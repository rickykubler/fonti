"""Cross-encoder reranking: scores (question, passage) pairs with full attention."""

from collections.abc import Sequence
from typing import Any, Protocol

from fonti.config import RerankSettings
from fonti.ml.hub import (
    MISSING_MODELS_MESSAGE,
    ModelUnavailableError,
    load_model,
    model_kwargs,
    resolve_device,
)


class Reranker(Protocol):
    @property
    def model_id(self) -> str: ...

    def score(self, question: str, passages: Sequence[str]) -> list[float]:
        """Relevance of each passage to the question, between 0 and 1."""
        ...


class CrossEncoderReranker:
    def __init__(self, settings: RerankSettings, *, offline: bool = False) -> None:
        self._settings = settings
        self._offline = offline
        self._model: Any = None

    @property
    def model_id(self) -> str:
        return self._settings.model

    def score(self, question: str, passages: Sequence[str]) -> list[float]:
        if not passages:
            return []
        scores = self._load().predict(
            [(question, passage) for passage in passages],
            batch_size=self._settings.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return [float(score) for score in scores]

    def _load(self) -> Any:
        if self._model is None:
            settings = self._settings

            def load(local_files_only: bool) -> Any:
                try:
                    from sentence_transformers import CrossEncoder
                except ImportError as exc:
                    raise ModelUnavailableError(MISSING_MODELS_MESSAGE) from exc
                device = resolve_device(settings.device)
                return CrossEncoder(
                    settings.model,
                    device=device,
                    revision=settings.revision,
                    local_files_only=local_files_only,
                    max_length=settings.max_length,
                    model_kwargs=model_kwargs(device),
                )

            self._model = load_model(load, settings.model, settings.revision, offline=self._offline)
        return self._model
