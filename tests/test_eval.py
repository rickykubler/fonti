import json
from pathlib import Path

import pypdfium2 as pdfium
import pytest

from fonti.config import EmbeddingSettings, Settings
from fonti.domain import BlockKind, Hit
from fonti.evaluation.corpus import Corpus, EvaluationError
from fonti.evaluation.dataset import (
    Evidence,
    Location,
    check_dataset,
    load_dataset,
    load_questions,
)
from fonti.evaluation.judge import Judge
from fonti.evaluation.metrics import (
    character_error_rate,
    evidence_ranks,
    quote_score,
    recall_at,
    reciprocal_rank,
)
from fonti.evaluation.report import write_report
from fonti.evaluation.runner import _groundedness, run
from fonti.service import Fonti
from tests.fakes import ScriptedChat
from tests.samples import CONTRACT_MD

RENT_QUOTE = "rate mensili anticipate di euro 800,00 ciascuna"

QUESTIONS = [
    {
        "id": "canone",
        "question": "Quanto si paga di canone ogni mese?",
        "answerable": True,
        "answer": "800 euro al mese",
        "evidence": [{"doc": "contratto", "page": 2, "quote": RENT_QUOTE}],
        "tags": ["contratto"],
    },
    {
        "id": "mondiali",
        "question": "Chi ha vinto i Mondiali del 2006?",
        "answerable": False,
        "tags": ["non-rispondibile"],
    },
]


def hit(doc_id: str, text: str, page: int = 1) -> Hit:
    return Hit(1, doc_id, "f.pdf", None, text, 0, len(text), page, page, "", BlockKind.TEXT)


@pytest.fixture
def eval_dir(tmp_path: Path) -> Path:
    root = tmp_path / "eval"
    (root / "corpus" / "synthetic").mkdir(parents=True)
    (root / "corpus" / "synthetic" / "contratto.md").write_text(CONTRACT_MD, encoding="utf-8")
    (root / "corpus" / "manifest.toml").write_text(
        """
[[document]]
id = "contratto"
title = "Contratto di locazione"
kind = "contratto"
source = "synthetic/contratto.md"
file = "contratto.pdf"
license = "CC0"

[[document]]
id = "contratto-scan"
title = "Contratto (scansione)"
kind = "scansione"
scan_of = "contratto"
file = "contratto_scan.pdf"
license = "CC0"
""",
        encoding="utf-8",
    )
    datasets = root / "datasets"
    datasets.mkdir()
    (datasets / "questions.jsonl").write_text(
        "\n".join(json.dumps(q, ensure_ascii=False) for q in QUESTIONS), encoding="utf-8"
    )
    (datasets / "main.toml").write_text(
        'documents = ["contratto"]\nquestions = "questions.jsonl"\n', encoding="utf-8"
    )
    (datasets / "scans.toml").write_text(
        'documents = ["contratto-scan"]\nquestions = "questions.jsonl"\n'
        'aliases = { contratto = "contratto-scan" }\n',
        encoding="utf-8",
    )
    return root


def test_quote_score_is_exact_or_fuzzy() -> None:
    text = "Il canone è pagato in dodici rate mensili anticipate di euro 800,00 ciascuna."

    assert quote_score("RATE  mensili anticipate", text) == 100.0
    assert quote_score("rate mensili antlcipate di curo 800,00", text) > 90
    assert quote_score("deposito cauzionale", text) < 70


def test_quote_score_requires_the_same_numbers() -> None:
    text = "Tasso di disoccupazione 5,2 | Tasso di occupazione 62,0"

    assert quote_score("Tasso di disoccupazione 5,8", text) == 0.0
    assert quote_score("Tasso di disoccupazione 5.2", text) > 90


def test_evidence_ranks_recall_and_mrr() -> None:
    evidence = [Evidence("contratto", 2, RENT_QUOTE), Evidence("contratto", 3, "recedere")]
    hits = [
        hit("x", "altro"),
        hit("sha", f"... {RENT_QUOTE} ...", page=5),  # same quote, wrong page
        hit("sha", f"... {RENT_QUOTE} ...", page=2),
        hit("other", "recedere"),
    ]

    ranks = evidence_ranks(evidence, hits, {"sha": "contratto", "other": "altro"}.get)

    assert ranks == [3, None]
    assert recall_at(ranks, 1) == 0.0
    assert recall_at(ranks, 5) == 0.5
    assert reciprocal_rank(ranks) == 1 / 3


def test_quotes_match_flat_text_and_markdown_tables() -> None:
    table = "| Voce | Valore |\n|---|---|\n| Disoccupati | 761 | -33 | -4,2 |"

    assert quote_score("Disoccupati 761 -33 -4,2", table) == 100.0


def test_any_location_of_an_evidence_counts() -> None:
    evidence = [
        Evidence(
            "istat",
            1,
            "il tasso scende al 5,8%",
            (Location("istat", 3, "Tasso di disoccupazione 5,8"),),
        )
    ]
    hits = [hit("sha", "altro"), hit("sha", "Tasso di disoccupazione 5,8 -0,1", page=3)]

    assert evidence_ranks(evidence, hits, {"sha": "istat"}.get) == [2]


def test_character_error_rate() -> None:
    assert character_error_rate("Il canone", "il  canone") == 0.0
    assert character_error_rate("Il canane", "Il canone") == pytest.approx(1 / 9)


def test_questions_are_validated(tmp_path: Path) -> None:
    path = tmp_path / "q.jsonl"
    path.write_text(json.dumps({"id": "a", "question": "?", "answerable": True}), "utf-8")

    with pytest.raises(EvaluationError, match="evidenze"):
        load_questions(path)


def test_aliases_reuse_questions_on_scans(eval_dir: Path) -> None:
    dataset = load_dataset(eval_dir / "datasets", "scans")

    assert [q.id for q in dataset.questions] == ["canone", "mondiali"]
    assert dataset.questions[0].evidence[0].doc == "contratto-scan"


def test_corpus_renders_synthetic_documents_and_scans(eval_dir: Path) -> None:
    corpus = Corpus(eval_dir / "corpus")

    actions = dict(corpus.prepare())

    assert actions == {"contratto": "generato", "contratto-scan": "scansione generata"}
    scan = pdfium.PdfDocument(corpus.path("contratto-scan"))
    try:
        assert len(scan) == 3
        assert scan[0].get_textpage().get_text_range().strip() == ""  # no text layer
    finally:
        scan.close()
    assert dict(corpus.prepare()) == {"contratto": "presente", "contratto-scan": "presente"}


def test_check_dataset_reports_wrong_pages_and_missing_quotes(eval_dir: Path) -> None:
    corpus = Corpus(eval_dir / "corpus")
    list(corpus.prepare(["contratto"]))
    wrong_page = {"doc": "contratto", "page": 1, "quote": RENT_QUOTE}
    missing = {"doc": "contratto", "page": 2, "quote": "testo inventato"}
    lines = [
        json.dumps({"id": "canone", "question": "?", "answerable": True, "evidence": [wrong_page]}),
        json.dumps({"id": "x", "question": "?", "answerable": True, "evidence": [missing]}),
    ]
    (eval_dir / "datasets" / "questions.jsonl").write_text("\n".join(lines), encoding="utf-8")

    problems = check_dataset(load_dataset(eval_dir / "datasets", "main"), corpus)

    assert problems == [
        "canone: citazione a pagina [2], non a pagina 1",
        "x: citazione non trovata in contratto: «testo inventato»",
    ]


def test_run_computes_metrics_and_writes_reports(eval_dir: Path) -> None:
    corpus = Corpus(eval_dir / "corpus")
    list(corpus.prepare(["contratto"]))

    def answer(prompt: str) -> str:
        if "Mondiali" in prompt:
            return "NON_TROVATO"
        return "Il canone si paga in dodici rate mensili di euro 800,00 [1]."

    def verdict(prompt: str) -> str:
        return "CORRETTA" if "RISPOSTA ATTESA" in prompt else "SUPPORTATA"

    settings = Settings(embedding=EmbeddingSettings(model="hashing"))
    result = run(
        load_dataset(eval_dir / "datasets", "main"),
        corpus,
        settings,
        work_dir=eval_dir / ".work",
        label="prova",
        judge=Judge(ScriptedChat(verdict)),
        fonti_factory=lambda s: Fonti(s, chat=ScriptedChat(answer)),
    )

    summary = result.summary()
    assert summary["recall@5"] == 1.0
    assert summary["correct_refusals"] == 1.0
    assert summary["false_refusals"] == 0.0
    assert summary["page_precision"] == 1.0
    assert summary["cites_evidence"] == 1.0
    assert summary["groundedness"] == 1.0
    assert summary["correctness"] == 1.0
    markdown, data = write_report(result, eval_dir / "reports")
    assert "| Recall@5 | 1 |" in markdown.read_text(encoding="utf-8")
    assert json.loads(data.read_text(encoding="utf-8"))["summary"]["recall@5"] == 1.0


def test_run_requires_prepared_documents(eval_dir: Path) -> None:
    with pytest.raises(EvaluationError, match="eval corpus"):
        run(
            load_dataset(eval_dir / "datasets", "main"),
            Corpus(eval_dir / "corpus"),
            Settings(embedding=EmbeddingSettings(model="hashing")),
            work_dir=eval_dir / ".work",
            label="x",
            generate=False,
        )


def test_groundedness_judges_every_sentence_on_its_cited_passages() -> None:
    from fonti.generation.citations import build_answer
    from tests.test_citations import hits, pages

    # Both sentences align to the same source sentence: one citation, two claims.
    answer = build_answer(
        "Come si paga?",
        "Si pagano dodici rate mensili [1]. Ogni rata è di euro 800,00 [1].",
        hits(),
        pages,
        0.3,
    )
    prompts: list[str] = []

    def verdict(prompt: str) -> str:
        prompts.append(prompt)
        return "SUPPORTATA"

    assert len(answer.citations) == 1
    assert _groundedness(Judge(ScriptedChat(verdict)), answer) == 1.0
    assert len(prompts) == 2
