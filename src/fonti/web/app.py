"""Web UI and JSON API (FastAPI + Jinja2 + HTMX).

Local by design: the server listens on 127.0.0.1 and rejects requests addressed to other
hosts (DNS rebinding) or coming from other origins (CSRF from a web page).
"""

import json
import re
import threading
from collections.abc import Awaitable, Callable, Iterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from fonti import __version__
from fonti.config import Settings
from fonti.domain import Answer
from fonti.errors import FontiError
from fonti.ingest.parsers import SUPPORTED_SUFFIXES
from fonti.service import DocumentLookupError, Fonti
from fonti.web.jobs import IngestJobs
from fonti.web.preview import render_page

_HERE = Path(__file__).parent
_DOC_ID = re.compile(r"[0-9a-f]{64}")
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


def create_app(settings: Settings, *, fonti: Fonti | None = None) -> FastAPI:
    service = fonti or Fonti(settings)
    lock = threading.Lock()  # one model call at a time: a single-user, local application
    jobs = IngestJobs(service, lock)
    templates = Jinja2Templates(directory=_HERE / "templates")
    templates.env.globals["version"] = __version__

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> Any:
        yield
        jobs.shutdown()
        service.close()

    app = FastAPI(title="fonti", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "::1"]
    )

    @app.middleware("http")
    async def same_origin_only(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method in _UNSAFE_METHODS and not _same_origin(request):
            return Response("Richiesta da un'altra origine rifiutata.", status_code=403)
        if _cross_site_subresource(request):
            # Another site embedding /documents/... could learn which files are indexed.
            return Response("Richiesta da un altro sito rifiutata.", status_code=403)
        response = await call_next(request)
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        return response

    app.mount("/static", StaticFiles(directory=_HERE / "static"), name="static")

    # --- pages ----------------------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    def ask_page(request: Request) -> Response:
        return templates.TemplateResponse(
            request, "ask.html", {"documents": len(service.documents())}
        )

    @app.get("/documents", response_class=HTMLResponse)
    def documents_page(request: Request) -> Response:
        return templates.TemplateResponse(
            request,
            "documents.html",
            {
                "documents": service.documents(),
                "jobs": jobs.recent(),
                "busy": jobs.busy(),
                "suffixes": ", ".join(sorted(SUPPORTED_SUFFIXES)),
                "max_upload_mb": settings.web.max_upload_mb,
            },
        )

    @app.get("/documents/list", response_class=HTMLResponse)
    def documents_list(request: Request) -> Response:
        return templates.TemplateResponse(
            request, "_documents.html", {"documents": service.documents()}
        )

    @app.get("/documents/jobs", response_class=HTMLResponse)
    def jobs_list(request: Request) -> Response:
        return templates.TemplateResponse(
            request, "_jobs.html", {"jobs": jobs.recent(), "busy": jobs.busy()}
        )

    @app.post("/documents", response_class=HTMLResponse)
    async def upload(request: Request, files: list[UploadFile]) -> Response:
        limit = settings.web.max_upload_mb * 1024 * 1024
        errors = []
        for file in files:
            name = Path(file.filename or "documento").name
            if Path(name).suffix.lower() not in SUPPORTED_SUFFIXES:
                errors.append(f"{name}: formato non supportato")
                continue
            content = await file.read(limit + 1)
            if len(content) > limit:
                errors.append(f"{name}: supera {settings.web.max_upload_mb} MB")
                continue
            jobs.submit(name, content)
        return templates.TemplateResponse(
            request, "_jobs.html", {"jobs": jobs.recent(), "busy": jobs.busy(), "errors": errors}
        )

    @app.delete("/documents/{doc_id}", response_class=HTMLResponse)
    def delete_document(request: Request, doc_id: str) -> Response:
        _check_id(doc_id)
        with lock:
            try:
                service.remove(doc_id)
            except DocumentLookupError as exc:
                raise HTTPException(404, str(exc)) from exc
        return templates.TemplateResponse(
            request, "_documents.html", {"documents": service.documents()}
        )

    @app.get("/documents/{doc_id}/file")
    def document_file(doc_id: str) -> Response:
        _check_id(doc_id)
        path = service.stored_file(doc_id)
        if path is None or not path.is_file():
            raise HTTPException(404, "Documento non trovato")
        info = service.find_document(doc_id)
        return FileResponse(
            path,
            media_type=_MEDIA_TYPES.get(path.suffix, "application/octet-stream"),
            filename=info.filename,
            content_disposition_type="inline",
        )

    @app.get("/documents/{doc_id}/pages/{page}.png")
    def page_preview(doc_id: str, page: int, start: int = -1, end: int = -1) -> Response:
        _check_id(doc_id)
        path = service.stored_file(doc_id)
        if path is None or path.suffix != ".pdf" or not path.is_file():
            raise HTTPException(404, "Anteprima disponibile solo per i PDF")
        text = service.store.document_text(doc_id) or ""
        passage = text[start:end] if 0 <= start < end <= len(text) else ""
        try:
            png = render_page(path, page, passage)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        return Response(png, media_type="image/png", headers={"Cache-Control": "max-age=3600"})

    # --- JSON API -------------------------------------------------------------------------

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "version": __version__, "documents": len(service.documents())}

    @app.get("/api/documents")
    def api_documents() -> list[dict[str, Any]]:
        return [asdict(doc) for doc in service.documents()]

    @app.post("/api/ask")
    def api_ask(body: AskRequest) -> dict[str, Any]:
        with lock:
            try:
                return asdict(service.ask(body.question))
            except FontiError as exc:
                raise HTTPException(503, str(exc)) from exc

    @app.post("/api/ask/stream")
    def api_ask_stream(body: AskRequest) -> StreamingResponse:
        """NDJSON events: {"type": "token"} while the model writes (provisional text), then
        {"type": "answer"} with the verified answer, or {"type": "error"}."""

        def events() -> Iterator[str]:
            with lock:
                try:
                    retrieval = service.retrieve(body.question)
                    for item in service.stream_answer(retrieval):
                        if isinstance(item, Answer):
                            yield _event("answer", answer=asdict(item))
                        else:
                            yield _event("token", text=item)
                except FontiError as exc:
                    yield _event("error", message=str(exc))

        return StreamingResponse(events(), media_type="application/x-ndjson")

    return app


def _event(kind: str, **data: Any) -> str:
    return json.dumps({"type": kind, **data}, ensure_ascii=False) + "\n"


def _check_id(doc_id: str) -> None:
    if not _DOC_ID.fullmatch(doc_id):
        raise HTTPException(404, "Documento non trovato")


def _cross_site_subresource(request: Request) -> bool:
    """A request made by another site's page (image, script, fetch), not a link the user
    followed: browsers send Sec-Fetch-Site and Sec-Fetch-Mode on every request."""
    return (
        request.headers.get("sec-fetch-site") == "cross-site"
        and request.headers.get("sec-fetch-mode") != "navigate"
    )


def _same_origin(request: Request) -> bool:
    if request.headers.get("sec-fetch-site") == "cross-site":
        return False
    origin = request.headers.get("origin")
    if origin is None:
        return True  # not a browser cross-origin request (e.g. curl, scripts on this machine)
    return urlsplit(origin).netloc == request.headers.get("host")
