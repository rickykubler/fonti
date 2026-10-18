from pathlib import Path

import pytest

from fonti.domain import BlockKind
from fonti.evaluation.synthetic import render_pdf
from fonti.ingest.parsers import ParseError, _clean_title, drop_running_headers, parse_file
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


TEXTS = [
    "Il presente regolamento stabilisce norme relative alla protezione dei dati.",
    "Il trattamento è lecito solo se ricorre almeno una delle condizioni seguenti.",
    "Il titolare del trattamento deve essere in grado di dimostrare il consenso.",
    "L'interessato ha il diritto di ottenere la rettifica dei dati inesatti.",
    "Ciascuno Stato membro dispone che una o più autorità pubbliche indipendenti vigilino.",
    "Le sanzioni sono effettive, proporzionate e dissuasive.",
]


def test_headers_alternating_between_even_and_odd_pages_are_dropped() -> None:
    def page(n: int) -> list[str]:
        header = (
            f"{n}.5.2016 IT Gazzetta ufficiale dell'Unione europea L 119/{n}"
            if n % 2
            else f"L 119/{n} IT Gazzetta ufficiale dell'Unione europea {n}.5.2016"
        )
        return [header, f"Articolo {n}", TEXTS[n - 1]]

    cleaned = drop_running_headers([page(n) for n in range(1, 7)])

    assert cleaned[0] == ["Articolo 1", TEXTS[0]]
    assert cleaned[1] == ["Articolo 2", TEXTS[1]]


def test_long_titles_are_shortened() -> None:
    raw = (
        "REGOLAMENTO  (UE)  2016/  679  DEL  PARLAMENTO  EUROPEO " + "relativo alla protezione " * 8
    )

    title = _clean_title(raw)

    assert title is not None
    assert title.startswith("REGOLAMENTO (UE) 2016/ 679 DEL PARLAMENTO EUROPEO relativo")
    assert len(title) <= 121
    assert title.endswith("\N{HORIZONTAL ELLIPSIS}")
    assert _clean_title("  ") is None


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
