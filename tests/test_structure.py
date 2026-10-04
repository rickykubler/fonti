import pytest

from fonti.domain import BlockKind
from fonti.ingest.structure import collapse_letter_spacing, heading_level, lines_to_blocks

LONG = "Nessuno può essere distolto dal giudice naturale precostituito per legge e la legge "


@pytest.mark.parametrize(
    ("line", "level"),
    [
        ("Art. 13", 5),
        ("Art. 13.", 5),
        ("Art. 1 - Oggetto", 5),
        ("Articolo 17", 5),
        ("Art. 2-bis", 5),
        ("PARTE PRIMA", 1),
        ("TITOLO I", 2),
        ("CAPO II", 3),
        ("Sezione III", 4),
        ("PRINCIPI FONDAMENTALI", 1),
        ("1. Oggetto del contratto", 6),
        ("2.1 Durata", 7),
        ("Art. 13 della Costituzione stabilisce che", 0),
        ("1. La libertà personale è inviolabile.", 0),
        ("Il canone è di euro 800.", 0),
        ("Capo di buona speranza", 0),
    ],
)
def test_heading_level(line: str, level: int) -> None:
    assert heading_level(line) == level


@pytest.mark.parametrize(
    ("line", "collapsed"),
    [
        ("P A R T E I", "PARTE I"),
        ("P A R T E I I", "PARTE II"),
        ("I N D I C E", "INDICE"),
        ("a b c", "a b c"),
        ("Art. 13", "Art. 13"),
    ],
)
def test_collapse_letter_spacing(line: str, collapsed: str) -> None:
    assert collapse_letter_spacing(line) == collapsed


def test_letter_spaced_part_heading_takes_its_title() -> None:
    blocks = lines_to_blocks(["P A R T E I", "DIRITTI E DOVERI DEI CITTADINI"], page=6)

    assert [(b.kind, b.text, b.level) for b in blocks] == [
        (BlockKind.HEADING, "PARTE I\nDIRITTI E DOVERI DEI CITTADINI", 1)
    ]


def test_bare_headings_absorb_their_title_line() -> None:
    lines = [
        "TITOLO I",
        "RAPPORTI CIVILI",
        "Articolo 17",
        "Diritto alla cancellazione",
        LONG + "punisce chiunque.",
    ]

    blocks = lines_to_blocks(lines, page=3)

    assert [(b.kind, b.text, b.level) for b in blocks[:2]] == [
        (BlockKind.HEADING, "TITOLO I\nRAPPORTI CIVILI", 2),
        (BlockKind.HEADING, "Articolo 17\nDiritto alla cancellazione", 5),
    ]
    assert blocks[2].kind is BlockKind.TEXT
    assert all(block.page == 3 for block in blocks)


def test_sentence_lines_are_not_titles() -> None:
    blocks = lines_to_blocks(["Art. 1.", "L'Italia è una Repubblica democratica."], page=1)

    assert [b.kind for b in blocks] == [BlockKind.HEADING, BlockKind.TEXT]


def test_paragraphs_join_lines_and_split_on_short_endings_and_list_items() -> None:
    lines = [
        LONG + "ammette la contrat-",
        "tazione collettiva.",
        LONG + "nuovo paragrafo",
        "che continua qui.",
        "a) prima lettera;",
        "b) seconda lettera.",
    ]

    texts = [block.text for block in lines_to_blocks(lines, page=1)]

    assert texts == [
        LONG + "ammette la contrattazione collettiva.",
        LONG + "nuovo paragrafo che continua qui.",
        "a) prima lettera;",
        "b) seconda lettera.",
    ]
