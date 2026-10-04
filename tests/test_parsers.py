from pathlib import Path

import pytest

from fonti.domain import BlockKind
from fonti.evaluation.synthetic import render_pdf
from fonti.ingest.parsers import ParseError, drop_running_headers, parse_file
from tests.samples import CONTRACT_MD


def test_pdf_pages_headings_and_paragraphs(tmp_path: Path) -> None:
    pdf = render_pdf(CONTRACT_MD, tmp_path / "contratto.pdf", title="Contratto di locazione")

    parsed = parse_file(pdf)

    assert parsed.page_count == 3
    assert parsed.title == "Contratto di locazione"
    headings = {b.text: b.page for b in parsed.blocks if b.kind is BlockKind.HEADING}
    assert headings["Art. 3 - Canone"] == 2
    assert headings["Art. 6 - Animali domestici"] == 3
    rent = next(b for b in parsed.blocks if "euro 800,00" in b.text)
    assert rent.page == 2
    assert rent.text.startswith("Il canone annuo è convenuto")
    assert rent.text.endswith("mediante bonifico bancario.")


def test_page_number_lines_are_dropped(tmp_path: Path) -> None:
    pdf = render_pdf("12\n\nIl testo del documento.\n\n- 3 -", tmp_path / "numeri.pdf")

    assert [b.text for b in parse_file(pdf).blocks] == ["Il testo del documento."]


def test_running_headers_and_page_counters_are_dropped() -> None:
    title = "Linee Guida sulla formazione dei documenti informatici"
    pages = [
        [title, f"{n} - 40", f"ART. {n}.", f"Testo della pagina {n}.", "OCCUPATI"]
        for n in range(1, 5)
    ]

    cleaned = drop_running_headers(pages)

    assert cleaned[0] == ["ART. 1.", "Testo della pagina 1."]
    assert cleaned[3] == ["ART. 4.", "Testo della pagina 4."]


def test_short_documents_keep_their_edges() -> None:
    pages = [["Intestazione", "Testo uno."], ["Intestazione", "Testo due."]]

    assert drop_running_headers(pages) == pages


def test_markdown_headings_and_paragraphs(tmp_path: Path) -> None:
    path = tmp_path / "note.md"
    path.write_text("# Verbale\n\nPrima riga\nseconda riga.\n\n## Punto 1\n\nTesto.\n", "utf-8")

    parsed = parse_file(path)

    assert [(b.kind, b.text) for b in parsed.blocks] == [
        (BlockKind.HEADING, "Verbale"),
        (BlockKind.TEXT, "Prima riga seconda riga."),
        (BlockKind.HEADING, "Punto 1"),
        (BlockKind.TEXT, "Testo."),
    ]


def test_unsupported_and_corrupt_files_raise_parse_error(tmp_path: Path) -> None:
    (tmp_path / "foglio.xlsx").write_bytes(b"x")
    (tmp_path / "rotto.pdf").write_bytes(b"not a pdf")

    with pytest.raises(ParseError, match="Formato non supportato"):
        parse_file(tmp_path / "foglio.xlsx")
    with pytest.raises(ParseError, match="Impossibile aprire"):
        parse_file(tmp_path / "rotto.pdf")
