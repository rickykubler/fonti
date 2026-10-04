"""Loading Hugging Face models without network traffic once they are cached.

Hugging Face libraries read `HF_HUB_OFFLINE` when they are imported, and even with
`local_files_only=True` they may contact the Hub. So the decision is taken before the first
import: if the model is already in the local cache, the process goes offline.
"""

import logging
import os
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from fonti.errors import FontiError

logger = logging.getLogger(__name__)

MISSING_MODELS_MESSAGE = (
    "I modelli locali non sono installati: esegui `uv sync --extra cpu` "
    "(oppure `uv sync --extra gpu` con una GPU NVIDIA)."
)

# Files never needed by sentence-transformers on PyTorch.
_IGNORED_FILES = ["*.onnx", "onnx/*", "openvino/*", "*.h5", "*.msgpack", "*.ot", "*.jpg", "*.png"]


class ModelUnavailableError(FontiError):
    """Local models cannot be loaded (missing extras or files)."""


def load_model[T](
    load: Callable[[bool], T], name: str, revision: str | None, *, offline: bool
) -> T:
    """Call `load(local_files_only)`: from the cache with the Hub disabled when the model is
    cached, otherwise downloading it (unless `offline`)."""
    cached = is_cached(name, revision)
    if not cached and offline:
        raise ModelUnavailableError(
            f"Il modello {name} non è nella cache locale e la modalità offline è attiva: "
            "esegui `fonti models pull` con la rete disponibile."
        )
    prepare_environment(offline=offline or cached)
    if not cached:
        logger.warning("Downloading %s from the Hugging Face Hub", name)
    try:
        return load(cached)
    except (OSError, ValueError) as exc:
        raise ModelUnavailableError(
            f"Impossibile caricare il modello {name}: {exc}. Prova `fonti models pull`."
        ) from exc


def pull(names: Sequence[tuple[str, str | None]]) -> list[Path]:
    """Download models (name, revision) into the Hugging Face cache."""
    prepare_environment(offline=False)
    from huggingface_hub import snapshot_download

    return [
        Path(snapshot_download(name, revision=revision, ignore_patterns=_IGNORED_FILES))
        for name, revision in names
        if not Path(name).is_dir()
    ]


def is_cached(name: str, revision: str | None = None) -> bool:
    """True if `name` is a local folder or a snapshot in the Hugging Face cache."""
    if Path(name).is_dir():
        return True
    repo = hub_cache_dir() / f"models--{name.replace('/', '--')}"
    ref = repo / "refs" / (revision or "main")
    commit = ref.read_text(encoding="utf-8").strip() if ref.is_file() else (revision or "")
    snapshot = repo / "snapshots" / commit
    return bool(commit) and (snapshot / "config.json").is_file()


def hub_cache_dir() -> Path:
    if "HF_HUB_CACHE" in os.environ:
        return Path(os.environ["HF_HUB_CACHE"])
    if "HF_HOME" in os.environ:
        return Path(os.environ["HF_HOME"]) / "hub"
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return cache / "huggingface" / "hub"


def prepare_environment(*, offline: bool) -> None:
    """Quiet, telemetry-free Hugging Face libraries; effective only before they are imported."""
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    if offline:
        os.environ["HF_HUB_OFFLINE"] = "1"


def resolve_device(device: str) -> str:
    if device != "auto":
        return device
    try:
        import torch
    except ImportError as exc:
        raise ModelUnavailableError(MISSING_MODELS_MESSAGE) from exc
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def model_kwargs(device: str) -> dict[str, Any]:
    """Half precision on CUDA: about twice as fast and half the memory, same rankings."""
    if not device.startswith("cuda"):
        return {}
    import torch

    return {"dtype": torch.float16}
