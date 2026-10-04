"""Text embedders: sentence-transformers models run locally, or a hashing embedder for tests."""

import hashlib
import math
import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray

from fonti.config import EmbeddingSettings
from fonti.ml.hub import (
    MISSING_MODELS_MESSAGE,
    ModelUnavailableError,
    load_model,
    model_kwargs,
    resolve_device,
)

_WORD_RE = re.compile(r"\w+")


class Embedder(Protocol):
    @property
    def model_id(self) -> str: ...

    def embed_documents(self, texts: Sequence[str]) -> NDArray[np.float32]: ...

    def embed_queries(self, texts: Sequence[str]) -> NDArray[np.float32]: ...


class HashingEmbedder:
    """Bag-of-words vectors through feature hashing: lexical only, no download.

    Meant for tests and quick trials, not for real use.
    """

    def __init__(self, dim: int = 512) -> None:
        self.dim = dim

    @property
    def model_id(self) -> str:
        return f"hashing:{self.dim}"

    def embed_documents(self, texts: Sequence[str]) -> NDArray[np.float32]:
        return self._embed(texts)

    def embed_queries(self, texts: Sequence[str]) -> NDArray[np.float32]:
        return self._embed(texts)

    def _embed(self, texts: Sequence[str]) -> NDArray[np.float32]:
        matrix = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for token, count in Counter(_fold(text)).items():
                digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
                value = int.from_bytes(digest, "little")
                sign = 1.0 if value >> 63 else -1.0
                matrix[row, value % self.dim] += sign * (1.0 + math.log(count))
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return (matrix / np.where(norms == 0, 1, norms)).astype(np.float32)


class SentenceTransformerEmbedder:
    """A sentence-transformers model, loaded on first use."""

    def __init__(self, settings: EmbeddingSettings, *, offline: bool = False) -> None:
        self._settings = settings
        self._offline = offline
        self._model: Any = None

    @property
    def model_id(self) -> str:
        revision = self._settings.revision
        return self._settings.model if revision is None else f"{self._settings.model}@{revision}"

    def embed_documents(self, texts: Sequence[str]) -> NDArray[np.float32]:
        return self._encode(texts, self._settings.document_prefix, query=False)

    def embed_queries(self, texts: Sequence[str]) -> NDArray[np.float32]:
        return self._encode(texts, self._settings.query_prefix, query=True)

    def _encode(self, texts: Sequence[str], prefix: str, *, query: bool) -> NDArray[np.float32]:
        model = self._load()
        if not texts:
            return np.empty((0, model.get_embedding_dimension()), dtype=np.float32)
        encode = model.encode_query if query else model.encode_document
        vectors = encode(
            [prefix + text for text in texts],
            batch_size=self._settings.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)

    def _load(self) -> Any:
        if self._model is None:
            settings = self._settings

            def load(local_files_only: bool) -> Any:
                try:
                    from sentence_transformers import SentenceTransformer
                except ImportError as exc:
                    raise ModelUnavailableError(MISSING_MODELS_MESSAGE) from exc
                device = resolve_device(settings.device)
                return SentenceTransformer(
                    settings.model,
                    device=device,
                    revision=settings.revision,
                    local_files_only=local_files_only,
                    model_kwargs=model_kwargs(device),
                )

            self._model = load_model(load, settings.model, settings.revision, offline=self._offline)
        return self._model


def create_embedder(settings: EmbeddingSettings, *, offline: bool = False) -> Embedder:
    """`model = "hashing"` (or "hashing:<dim>") selects the download-free hashing embedder."""
    name = settings.model
    if name == "hashing" or name.startswith("hashing:"):
        _, _, dim = name.partition(":")
        return HashingEmbedder(int(dim) if dim else 512)
    return SentenceTransformerEmbedder(settings, offline=offline)


def _fold(text: str) -> list[str]:
    """Lowercase words without accents."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return [word for word in _WORD_RE.findall(stripped) if len(word) > 1 or word.isdigit()]
