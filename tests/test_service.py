from collections.abc import Iterator
from pathlib import Path

import pytest

from fonti.config import EmbeddingSettings, Settings
from fonti.evaluation.synthetic import render_pdf
from fonti.index.store import IndexMismatchError
from fonti.service import (
    DocumentLookupError,
    Fonti,
    IngestResult,
    IngestStatus,
    ReindexIncompleteError,
)
from tests.fakes import FakeChat
from tests.samples import CONTRACT_MD


def settings(data_dir: Path, embedder: str = "hashing") -> Settings:
    return Settings(data_dir=data_dir, embedding=EmbeddingSettings(model=embedder))


@pytest.fixture
def contract_pdf(tmp_path: Path) -> Path:
    return render_pdf(CONTRACT_MD, tmp_path / "contratto.pdf", title="Contratto di locazione")


@pytest.fixture
def fonti(tmp_path: Path) -> Iterator[Fonti]:
    with Fonti(settings(tmp_path / "data")) as service:
        yield service


def test_ingest_adds_a_document_once(fonti: Fonti, contract_pdf: Path) -> None:
    [first] = fonti.ingest([contract_pdf])
    [second] = fonti.ingest([contract_pdf])

    assert first.status is IngestStatus.ADDED
    assert first.chunks > 0
    assert second.status is IngestStatus.SKIPPED
    [info] = fonti.documents()
    assert (info.title, info.page_count, info.filename) == (
        "Contratto di locazione",
        3,
        "contratto.pdf",
    )
    stored = fonti.stored_file(info.id)
    assert stored is not None
    assert stored.read_bytes() == contract_pdf.read_bytes()


def test_ingest_folder_reports_each_file(fonti: Fonti, tmp_path: Path, contract_pdf: Path) -> None:
    folder = tmp_path / "docs"
    (folder / "sub").mkdir(parents=True)
    (folder / "sub" / "contratto.pdf").write_bytes(contract_pdf.read_bytes())
    (folder / "verbale.md").write_text("# Verbale\n\nSi approva il bilancio.\n", "utf-8")
    (folder / "rotto.pdf").write_bytes(b"not a pdf")
    (folder / "foglio.xlsx").write_bytes(b"ignored")

    results = {r.path.name: r.status for r in fonti.ingest([folder])}

    assert results == {
        "rotto.pdf": IngestStatus.FAILED,
        "contratto.pdf": IngestStatus.ADDED,
        "verbale.md": IngestStatus.ADDED,
    }


def test_search_finds_the_rent_article_and_its_page(fonti: Fonti, contract_pdf: Path) -> None:
    list(fonti.ingest([contract_pdf]))

    hits = fonti.search("Qual è il canone mensile da pagare?")

    assert "Art. 3 - Canone" in hits[0].section
    assert hits[0].page_start == 2
    assert hits[0].filename == "contratto.pdf"


def test_remove_by_id_prefix_deletes_the_stored_copy(fonti: Fonti, contract_pdf: Path) -> None:
    [result] = fonti.ingest([contract_pdf])
    assert result.doc_id is not None
    stored = fonti.stored_file(result.doc_id)

    fonti.remove(result.doc_id[:8])

    assert fonti.documents() == []
    assert stored is not None
    assert not stored.exists()
    with pytest.raises(DocumentLookupError):
        fonti.remove(result.doc_id[:8])


def test_changing_the_embedder_requires_a_reindex(tmp_path: Path, contract_pdf: Path) -> None:
    data_dir = tmp_path / "data"
    with Fonti(settings(data_dir, "hashing:256")) as service:
        list(service.ingest([contract_pdf]))

    with Fonti(settings(data_dir, "hashing:128")) as service:
        with pytest.raises(IndexMismatchError):
            service.search("canone")
        [result] = service.reindex()

        assert result.status is IngestStatus.UPDATED
        assert service.search("canone")


def test_reindex_with_a_missing_file_keeps_the_index_flagged(
    tmp_path: Path, contract_pdf: Path
) -> None:
    data_dir = tmp_path / "data"
    with Fonti(settings(data_dir, "hashing:256")) as service:
        [added] = service.ingest([contract_pdf])
    assert added.doc_id is not None

    with Fonti(settings(data_dir, "hashing:128")) as service:
        stored = service.stored_file(added.doc_id)
        assert stored is not None
        stored.unlink()
        results: list[IngestResult] = []
        with pytest.raises(ReindexIncompleteError):
            results.extend(service.reindex())

        assert [r.status for r in results] == [IngestStatus.FAILED]
        with pytest.raises(IndexMismatchError):
            service.search("canone")


def test_ask_returns_verified_citations(tmp_path: Path, contract_pdf: Path) -> None:
    chat = FakeChat("Il canone si paga in dodici rate mensili di euro 800,00 [1].")
    with Fonti(settings(tmp_path / "data"), chat=chat) as service:
        list(service.ingest([contract_pdf]))

        answer = service.ask("Quanto si paga di canone ogni mese?")

    assert not answer.abstained
    [citation] = answer.citations
    assert citation.page == 2
    assert "euro 800,00" in citation.passage
    prompt = chat.calls[0][1]["content"]
    assert "[1] Contratto di locazione, pagina 2" in prompt
    assert prompt.endswith("DOMANDA: Quanto si paga di canone ogni mese?")


def test_ask_abstains_when_the_model_finds_nothing(tmp_path: Path, contract_pdf: Path) -> None:
    with Fonti(settings(tmp_path / "data"), chat=FakeChat("NON_TROVATO")) as service:
        list(service.ingest([contract_pdf]))

        answer = service.ask("Chi ha vinto i Mondiali del 2006?")

    assert answer.abstained
    assert answer.text.startswith("Non lo so")


def test_ask_on_an_empty_index_abstains_without_calling_the_model(tmp_path: Path) -> None:
    chat = FakeChat("non dovrebbe essere chiamato")
    with Fonti(settings(tmp_path / "data"), chat=chat) as service:
        answer = service.ask("Qualsiasi domanda")

    assert answer.abstained
    assert chat.calls == []
