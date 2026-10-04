from collections.abc import Sequence
from pathlib import Path

import pytest

from fonti.config import EmbeddingSettings, RerankSettings, Settings
from fonti.evaluation.synthetic import render_pdf
from fonti.service import Fonti
from tests.fakes import FakeChat
from tests.samples import CONTRACT_MD


class KeywordReranker:
    """Scores 0.9 when the passage contains the keyword, 0.1 otherwise."""

    def __init__(self, keyword: str) -> None:
        self.keyword = keyword
        self.calls = 0

    @property
    def model_id(self) -> str:
        return "keyword"

    def score(self, question: str, passages: Sequence[str]) -> list[float]:
        self.calls += 1
        return [0.9 if self.keyword in passage else 0.1 for passage in passages]


def make(tmp_path: Path, reranker: KeywordReranker, min_score: float, chat: FakeChat) -> Fonti:
    settings = Settings(
        data_dir=tmp_path / "data",
        embedding=EmbeddingSettings(model="hashing"),
        rerank=RerankSettings(enabled=True, min_score=min_score),
    )
    service = Fonti(settings, reranker=reranker, chat=chat)
    list(service.ingest([render_pdf(CONTRACT_MD, tmp_path / "contratto.pdf")]))
    return service


def test_reranking_reorders_the_candidates(tmp_path: Path) -> None:
    with make(tmp_path, KeywordReranker("animali"), 0.0, FakeChat("x")) as service:
        retrieval = service.retrieve("Qual è il canone mensile?")

    assert "Animali domestici" in retrieval.ranked[0].section
    assert retrieval.ranked[0].score == 0.9
    assert retrieval.relevant
    assert {hit.chunk_id for hit in retrieval.ranked} == {
        hit.chunk_id for hit in retrieval.candidates
    }


def test_gate_abstains_without_calling_the_model(tmp_path: Path) -> None:
    chat = FakeChat("non dovrebbe essere chiamato")
    with make(tmp_path, KeywordReranker("parola assente"), 0.5, chat) as service:
        answer = service.ask("Chi ha vinto i Mondiali?")

    assert answer.abstained
    assert chat.calls == []


@pytest.mark.slow
def test_bge_reranker_prefers_the_relevant_passage() -> None:
    from fonti.ml.reranker import CrossEncoderReranker

    reranker = CrossEncoderReranker(RerankSettings(enabled=True))
    scores = reranker.score(
        "Quanto dura il mandato del Presidente della Repubblica?",
        ["Il Presidente della Repubblica è eletto per sette anni.", "Il domicilio è inviolabile."],
    )

    assert scores[0] > 0.5 > scores[1]
    assert all(0.0 <= score <= 1.0 for score in scores)
