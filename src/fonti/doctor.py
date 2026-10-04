"""Environment checks for `fonti doctor`: what is installed, cached and reachable."""

import importlib.util
import platform
from dataclasses import dataclass
from enum import StrEnum

import httpx

from fonti import __version__
from fonti.config import Settings
from fonti.generation.llm import RemoteEndpointError, ensure_local
from fonti.ml.hub import is_cached


class Status(StrEnum):
    OK = "OK"
    WARNING = "!!"
    FAILED = "KO"
    SKIPPED = "--"


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    status: Status
    detail: str


def run_checks(settings: Settings, *, transport: httpx.BaseTransport | None = None) -> list[Check]:
    checks = [
        Check("fonti", Status.OK, f"{__version__} su Python {platform.python_version()}"),
        _torch(),
        _model("Embedding", settings.embedding.model, settings.embedding.revision),
    ]
    if settings.rerank.enabled:
        checks.append(_model("Reranker", settings.rerank.model, settings.rerank.revision))
    else:
        checks.append(Check("Reranker", Status.SKIPPED, "disattivato (rerank.enabled = false)"))
    checks.append(_docling(settings))
    checks.extend(_llm(settings, transport))
    checks.append(Check("Dati", Status.OK, str(settings.data_dir)))
    return checks


def _torch() -> Check:
    if importlib.util.find_spec("torch") is None:
        return Check(
            "PyTorch", Status.FAILED, "non installato: `uv sync --extra gpu` oppure `--extra cpu`"
        )
    import torch

    if torch.cuda.is_available():
        return Check(
            "PyTorch", Status.OK, f"{torch.__version__}, GPU {torch.cuda.get_device_name(0)}"
        )
    return Check(
        "PyTorch", Status.WARNING, f"{torch.__version__} solo CPU: funziona, ma è più lento"
    )


def _model(label: str, name: str, revision: str | None) -> Check:
    if name.startswith("hashing"):
        return Check(label, Status.WARNING, f"{name}: solo per test, nessuna semantica")
    if is_cached(name, revision):
        return Check(label, Status.OK, f"{name} presente in locale")
    return Check(label, Status.FAILED, f"{name} non scaricato: `fonti models pull`")


def _docling(settings: Settings) -> Check:
    if importlib.util.find_spec("docling") is None:
        status = Status.SKIPPED if settings.parser.mode == "fast" else Status.WARNING
        return Check(
            "Docling",
            status,
            "non installato: scansioni e .docx non leggibili (`--extra docling`)",
        )
    from fonti.ingest.docling_parser import models_dir

    if models_dir().is_dir():
        return Check("Docling", Status.OK, f"modelli in {models_dir()}")
    return Check("Docling", Status.FAILED, "modelli non scaricati: `fonti models pull`")


def _llm(settings: Settings, transport: httpx.BaseTransport | None) -> list[Check]:
    llm = settings.llm
    try:
        ensure_local(llm)
        privacy = Check("Privacy", Status.OK, f"LLM locale su {llm.base_url}")
    except RemoteEndpointError:
        return [
            Check(
                "Privacy",
                Status.WARNING,
                f"LLM remoto su {llm.base_url}: domande e passaggi escono dal computer",
            )
        ]
    if llm.provider != "ollama":
        return [privacy, Check("LLM", Status.SKIPPED, f"{llm.provider}: controllo non disponibile")]
    try:
        with httpx.Client(base_url=llm.base_url, timeout=5, transport=transport) as client:
            response = client.get("/api/tags")
            response.raise_for_status()
            models = {model["name"] for model in response.json().get("models", [])}
    except httpx.HTTPError:
        return [
            privacy,
            Check("Ollama", Status.FAILED, f"non raggiungibile su {llm.base_url}: è avviato?"),
        ]
    name = llm.model if ":" in llm.model else f"{llm.model}:latest"
    if name in models:
        return [privacy, Check("Ollama", Status.OK, f"modello {llm.model} disponibile")]
    return [
        privacy,
        Check("Ollama", Status.FAILED, f"modello {llm.model} mancante: `ollama pull {llm.model}`"),
    ]
