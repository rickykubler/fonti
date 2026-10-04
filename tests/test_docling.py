from pathlib import Path

import pytest

from fonti.config import ParserSettings
from fonti.domain import BlockKind
from fonti.evaluation.corpus import make_scan
from fonti.evaluation.metrics import character_error_rate
from fonti.evaluation.synthetic import render_pdf
from fonti.ingest.parsers import parse_file
from tests.samples import CONTRACT_MD

pytestmark = pytest.mark.slow

TABLE_MD = """\
# Codici di errore

| Codice | Significato |
|---|---|
| E01 | Mancata accensione del bruciatore |
| E04 | Pressione dell'impianto insufficiente |
"""


def test_docling_reads_a_scanned_contract_with_ocr(tmp_path: Path) -> None:
    from fonti.ingest.docling_parser import DoclingParser, scanned_pages

    original = render_pdf(CONTRACT_MD, tmp_path / "contratto.pdf")
    scan = make_scan(original, tmp_path / "scan.pdf", seed="test")

    parsed = DoclingParser(ParserSettings(mode="docling")).parse(scan)

    assert scanned_pages(scan) == [1, 2, 3]
    assert parsed.ocr_pages == (1, 2, 3)
    ocr_text = "\n".join(b.text for b in parsed.blocks)
    reference = "\n".join(b.text for b in parse_file(original).blocks)
    assert character_error_rate(ocr_text, reference) < 0.1
    assert "800,00" in ocr_text


def test_docling_keeps_table_structure(tmp_path: Path) -> None:
    from fonti.ingest.docling_parser import DoclingParser

    pdf = render_pdf(TABLE_MD, tmp_path / "tabella.pdf")

    parsed = DoclingParser(ParserSettings(mode="docling")).parse(pdf)

    [table] = [b for b in parsed.blocks if b.kind is BlockKind.TABLE]
    assert "| E04 " in table.text
    assert "Pressione dell'impianto insufficiente" in table.text
