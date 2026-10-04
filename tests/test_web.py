import json
import time
from collections.abc import Iterator
from pathlib import Path

import pypdfium2 as pdfium
import pytest
from fastapi.testclient import TestClient

from fonti.config import EmbeddingSettings, Settings
from fonti.evaluation.synthetic import render_pdf
from fonti.service import Fonti
from fonti.web.app import create_app
from fonti.web.preview import merge_lines, passage_boxes
from tests.fakes import FakeChat
from tests.samples import CONTRACT_MD

ANSWER = "Il canone si paga in dodici rate mensili di euro 800,00 [1]."


@pytest.fixture
def contract(tmp_path: Path) -> Path:
    return render_pdf(CONTRACT_MD, tmp_path / "contratto.pdf", title="Contratto di locazione")


@pytest.fixture
def service(tmp_path: Path) -> Fonti:
    settings = Settings(data_dir=tmp_path / "data", embedding=EmbeddingSettings(model="hashing"))
    return Fonti(settings, chat=FakeChat(ANSWER))


@pytest.fixture
def client(service: Fonti) -> Iterator[TestClient]:
    app = create_app(service.settings, fonti=service)
    with TestClient(app, base_url="http://127.0.0.1") as test_client:
        yield test_client


def ingested_id(service: Fonti, contract: Path) -> str:
    [result] = service.ingest([contract])
    assert result.doc_id is not None
    return result.doc_id


def test_pages_render(client: TestClient) -> None:
    ask = client.get("/")
    documents = client.get("/documents")

    assert ask.status_code == 200
    assert "Fai una domanda ai tuoi documenti" in ask.text
    assert "Non hai ancora indicizzato documenti" in ask.text
    assert documents.status_code == 200
    assert "Nessun documento indicizzato" in documents.text


def test_upload_is_indexed_in_the_background(client: TestClient, contract: Path) -> None:
    response = client.post(
        "/documents", files=[("files", ("contratto.pdf", contract.read_bytes(), "application/pdf"))]
    )
    assert response.status_code == 200
    assert "contratto.pdf" in response.text

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and "completato" not in client.get("/documents/jobs").text:
        time.sleep(0.1)

    [document] = client.get("/api/documents").json()
    assert document["filename"] == "contratto.pdf"
    assert "Contratto di locazione" in client.get("/documents/list").text


def test_upload_rejects_unsupported_files(client: TestClient) -> None:
    response = client.post("/documents", files=[("files", ("virus.exe", b"MZ", "application/x"))])

    assert "virus.exe: formato non supportato" in response.text
    assert client.get("/api/documents").json() == []


def test_streamed_answer_ends_with_verified_citations(
    client: TestClient, service: Fonti, contract: Path
) -> None:
    ingested_id(service, contract)

    response = client.post("/api/ask/stream", json={"question": "Quanto è il canone mensile?"})

    events = [json.loads(line) for line in response.text.splitlines()]
    assert {event["type"] for event in events[:-1]} == {"token"}
    final = events[-1]["answer"]
    assert not final["abstained"]
    assert final["citations"][0]["page"] == 2
    assert "800,00" in final["citations"][0]["passage"]


def test_json_answer(client: TestClient, service: Fonti, contract: Path) -> None:
    ingested_id(service, contract)

    answer = client.post("/api/ask", json={"question": "Quanto è il canone mensile?"}).json()

    assert answer["text"] == ANSWER


def test_files_and_page_previews_are_served_by_id(
    client: TestClient, service: Fonti, contract: Path
) -> None:
    doc_id = ingested_id(service, contract)
    start = service.store.document_text(doc_id).index("dodici rate")  # type: ignore[union-attr]

    pdf = client.get(f"/documents/{doc_id}/file")
    preview = client.get(f"/documents/{doc_id}/pages/2.png?start={start}&end={start + 40}")

    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.headers["content-disposition"].startswith("inline")
    assert preview.status_code == 200
    assert preview.content.startswith(b"\x89PNG")
    assert client.get(f"/documents/{doc_id}/pages/9.png").status_code == 404
    assert client.get("/documents/not-an-id/file").status_code == 404
    assert client.get("/documents/..%2F..%2Fpyproject.toml/file").status_code == 404


def test_highlight_of_one_line_is_one_box(contract: Path) -> None:
    pdf = pdfium.PdfDocument(contract)
    page = pdf[0]
    try:
        boxes = passage_boxes(page, "La locazione ha durata di quattro anni, con decorrenza")
    finally:
        page.close()
        pdf.close()

    assert len(boxes) == 1


def test_merge_lines_keeps_other_lines_and_columns_apart() -> None:
    first = (10.0, 100.0, 50.0, 110.0)
    same_line = (53.0, 100.5, 90.0, 110.0)
    next_line = (10.0, 88.0, 60.0, 98.0)
    other_column = (300.0, 100.0, 340.0, 110.0)

    assert merge_lines([first, same_line]) == [(10.0, 100.0, 90.0, 110.0)]
    assert merge_lines([first, next_line]) == [first, next_line]
    assert merge_lines([first, other_column]) == [first, other_column]


def test_delete_document(client: TestClient, service: Fonti, contract: Path) -> None:
    doc_id = ingested_id(service, contract)

    response = client.delete(f"/documents/{doc_id}")

    assert response.status_code == 200
    assert client.get("/api/documents").json() == []


def test_requests_for_other_hosts_are_rejected(service: Fonti) -> None:
    app = create_app(service.settings, fonti=service)
    with TestClient(app, base_url="http://attacker.example") as foreign:
        assert foreign.get("/").status_code == 400


def test_cross_origin_writes_are_rejected(client: TestClient) -> None:
    question = {"question": "Qualsiasi"}

    foreign = client.post("/api/ask", json=question, headers={"Origin": "http://attacker.example"})
    same = client.post("/api/ask", json=question, headers={"Origin": "http://127.0.0.1"})

    assert foreign.status_code == 403
    assert same.status_code == 200
