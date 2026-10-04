"""Evaluation corpus: public documents (downloaded and verified by SHA-256), synthetic documents
rendered from Markdown, and synthetic scans made by rasterizing and degrading a PDF.

Synthetic scans have an exact ground truth (the text of the original), so OCR quality can be
measured. Building them needs the development dependencies (reportlab, Pillow).
"""

import hashlib
import io
import logging
import random
import shutil
import subprocess
import tomllib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import numpy as np

from fonti.errors import FontiError
from fonti.evaluation.synthetic import render_pdf

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; fonti-eval/0.1; +https://github.com/)"
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0 Safari/537.36"
)
SCAN_DPI = 200  # a common office scanner setting


class EvaluationError(FontiError):
    pass


@dataclass(frozen=True, slots=True)
class CorpusDocument:
    id: str
    title: str
    kind: str
    file: str
    license: str
    url: str | None = None
    sha256: str | None = None
    source: str | None = None  # Markdown of a synthetic document, relative to the corpus root
    scan_of: str | None = None  # id of the document this is a synthetic scan of


class Corpus:
    def __init__(self, root: Path) -> None:
        self.root = root
        manifest = root / "manifest.toml"
        if not manifest.is_file():
            raise EvaluationError(f"Manifest del corpus non trovato: {manifest}")
        with manifest.open("rb") as f:
            entries: list[dict[str, Any]] = tomllib.load(f)["document"]
        self.documents = {entry["id"]: CorpusDocument(**entry) for entry in entries}

    def path(self, doc_id: str) -> Path:
        return self.root / "files" / self.documents[doc_id].file

    def prepare(self, ids: Iterable[str] | None = None) -> Iterator[tuple[str, str]]:
        """Build the missing files; yields (document id, what was done)."""
        wanted = list(ids) if ids is not None else list(self.documents)
        # Originals first: scans are made from them.
        ordered = sorted(wanted, key=lambda doc_id: self.documents[doc_id].scan_of is not None)
        for doc_id in ordered:
            document = self.documents[doc_id]
            target = self.path(doc_id)
            if target.is_file():
                self._verify(document, target)
                yield doc_id, "presente"
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if document.scan_of is not None:
                if not self.path(document.scan_of).is_file():
                    yield from self.prepare([document.scan_of])
                make_scan(self.path(document.scan_of), target, seed=doc_id)
                yield doc_id, "scansione generata"
            elif document.source is not None:
                markdown = (self.root / document.source).read_text(encoding="utf-8")
                render_pdf(markdown, target, title=document.title)
                yield doc_id, "generato"
            elif document.url is not None:
                self._download(document, target)
                yield doc_id, "scaricato"
            else:
                raise EvaluationError(f"{doc_id}: manca url, source o scan_of nel manifest")

    def _download(self, document: CorpusDocument, target: Path) -> None:
        assert document.url is not None
        logger.info("Downloading %s", document.url)
        partial = target.with_suffix(target.suffix + ".part")
        response = httpx.get(
            document.url, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=120
        )
        partial.write_bytes(response.content if response.status_code == 200 else b"")
        if not _looks_like(target.suffix, partial):
            # Some sites (EUR-Lex) answer 202 with an empty body to non-browser TLS clients
            # but accept curl.
            _curl(document.url, partial)
        if not _looks_like(target.suffix, partial):
            partial.unlink(missing_ok=True)
            raise EvaluationError(
                f"{document.id}: download non riuscito da {document.url} "
                f"(HTTP {response.status_code}). Scaricalo a mano in {target}."
            )
        self._verify(document, partial)
        partial.replace(target)

    @staticmethod
    def _verify(document: CorpusDocument, path: Path) -> None:
        if document.sha256 is None:
            return
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != document.sha256:
            raise EvaluationError(
                f"{document.id}: SHA-256 inatteso ({digest}). Il documento è cambiato alla fonte: "
                "controllalo e aggiorna il manifest (e le domande che lo riguardano)."
            )


def _looks_like(suffix: str, path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    if suffix.lower() == ".pdf":
        with path.open("rb") as f:
            return f.read(5) == b"%PDF-"
    return True


def _curl(url: str, target: Path) -> None:
    curl = shutil.which("curl")
    if curl is None:
        return
    subprocess.run(
        [curl, "--silent", "--location", "--fail", "--max-time", "300", "--user-agent",
         BROWSER_USER_AGENT, "--output", str(target), url],
        check=False,
    )  # fmt: skip


def make_scan(source: Path, target: Path, *, seed: str, dpi: int = SCAN_DPI) -> Path:
    """Rasterize every page of `source` and degrade it like an office scan: grey levels, a
    slight rotation, blur, noise and JPEG compression. The result has no text layer."""
    import pypdfium2 as pdfium
    from PIL import Image, ImageFilter

    rng = random.Random(seed)
    noise = np.random.default_rng(rng.randrange(2**32))
    pages: list[Image.Image] = []
    pdf = pdfium.PdfDocument(source)
    try:
        for index in range(len(pdf)):
            page = pdf[index]
            try:
                image = page.render(scale=dpi / 72).to_pil().convert("L")
            finally:
                page.close()
            image = image.rotate(
                rng.uniform(-0.8, 0.8), resample=Image.Resampling.BICUBIC, fillcolor=255
            )
            image = image.filter(ImageFilter.GaussianBlur(radius=0.5))
            pixels = np.asarray(image, dtype=np.float32) + noise.normal(0, 10, image.size[::-1])
            image = Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8))
            buffer = io.BytesIO()
            image.save(buffer, "JPEG", quality=60)
            pages.append(Image.open(io.BytesIO(buffer.getvalue())))
    finally:
        pdf.close()
    pages[0].save(target, "PDF", resolution=dpi, save_all=True, append_images=pages[1:])
    return target
