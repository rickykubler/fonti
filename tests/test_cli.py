import json
from pathlib import Path

import pytest

from fonti import __version__
from fonti.cli import main
from fonti.evaluation.synthetic import render_pdf
from tests.fakes import FakeChat
from tests.samples import CONTRACT_MD


@pytest.fixture(autouse=True)
def _local_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FONTI_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FONTI_EMBEDDING__MODEL", "hashing")


@pytest.fixture
def contract_pdf(tmp_path: Path) -> Path:
    return render_pdf(CONTRACT_MD, tmp_path / "contratto.pdf", title="Contratto di locazione")


def test_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    assert exc_info.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_ingest_docs_and_remove(contract_pdf: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["ingest", str(contract_pdf)]) == 0
    assert "+ contratto.pdf" in capsys.readouterr().out

    assert main(["docs"]) == 0
    listing = capsys.readouterr().out
    assert "contratto.pdf — Contratto di locazione" in listing

    doc_id = listing.split()[0]
    assert main(["remove", doc_id]) == 0
    assert "Rimosso contratto.pdf" in capsys.readouterr().out


def test_ask_prints_answer_and_sources(
    contract_pdf: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    chat = FakeChat("Il canone si paga in dodici rate mensili di euro 800,00 [1].")
    monkeypatch.setattr("fonti.service.create_chat_client", lambda settings: chat)
    main(["ingest", str(contract_pdf)])
    capsys.readouterr()

    assert main(["ask", "Quanto si paga di canone ogni mese?"]) == 0

    output = capsys.readouterr().out
    assert output.startswith("Il canone si paga in dodici rate")
    assert "[1] Contratto di locazione — " in output
    assert "pag. 2: «" in output
    assert "euro 800,00" in output


def test_ask_json_output(
    contract_pdf: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "fonti.service.create_chat_client", lambda settings: FakeChat("NON_TROVATO")
    )
    main(["ingest", str(contract_pdf)])
    capsys.readouterr()

    assert main(["ask", "Chi ha vinto?", "--json"]) == 0

    data = json.loads(capsys.readouterr().out)
    assert data["abstained"] is True
    assert data["sources"][0]["filename"] == "contratto.pdf"


def test_user_errors_are_reported_without_traceback(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["remove", "abcdef"]) == 1

    assert capsys.readouterr().err.startswith("Errore: Nessun documento")


def test_ingest_failure_sets_exit_code(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    broken = tmp_path / "rotto.pdf"
    broken.write_bytes(b"not a pdf")

    assert main(["ingest", str(broken)]) == 1
    assert "! rotto.pdf: Impossibile aprire" in capsys.readouterr().out
