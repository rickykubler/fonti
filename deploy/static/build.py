"""Build the static demo of fonti: real answers computed in advance, with highlighted pages.

    uv run python deploy/static/build.py OUT_DIR [--config eval/configs/default.toml]

It downloads or renders the corpus documents it needs, indexes them in a temporary folder and
asks every question below with the given configuration, so it needs the models and Ollama like
`fonti ask`. OUT_DIR becomes a Hugging Face static Space: index.html, app.css and page images.
"""

import argparse
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from fonti import __version__
from fonti.config import load_settings
from fonti.domain import Answer
from fonti.evaluation.corpus import Corpus, CorpusDocument
from fonti.service import Fonti
from fonti.web.preview import render_page

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
REPO = "https://github.com/rickykubler/fonti"
DOCUMENTS = ["costituzione", "gdpr", "ai-act", "istat", "contratto", "verbale", "manuale"]
QUESTIONS = [
    (
        "Normative e documenti pubblici",
        [
            "Cosa deve fare chi pubblica un deep fake generato con l'IA?",
            "Qual è la sanzione massima per chi usa pratiche di IA vietate?",
            "Entro quanto tempo il titolare deve notificare una violazione dei dati personali "
            "all'autorità di controllo?",
            "Secondo il GDPR, a partire da quale età un minore può dare da solo il consenso al "
            "trattamento dei dati per i servizi online?",
            "Qual è la posizione dell'Italia nei confronti della guerra?",
            "Quanti anni bisogna avere per essere eletti Presidente della Repubblica e quanto "
            "dura il mandato?",
            "Qual è il tasso di disoccupazione giovanile a luglio 2026?",
        ],
    ),
    (
        "Contratto, verbale e manuale (documenti sintetici)",
        [
            "Chi paga la sostituzione della caldaia nell'appartamento in affitto?",
            "Si possono tenere animali domestici nell'appartamento?",
            "Quale preventivo è stato approvato per il rifacimento della facciata e per quale "
            "importo?",
            "Cosa significa il codice di errore E04 della caldaia e cosa bisogna fare?",
        ],
    ),
    (
        "Domande a cui i documenti non rispondono",
        [
            "Il contratto di locazione include un posto auto o un garage?",
            "Qual è la sanzione per chi non va a votare?",
            "Chi ha vinto il campionato di calcio di Serie A nel 2025?",
        ],
    ),
]
_MARKER = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")
_BULLET = re.compile(r"^[ \t]*[*-][ \t]+", re.MULTILINE)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--config", type=Path, default=ROOT / "eval/configs/default.toml")
    args = parser.parse_args()

    corpus = Corpus(ROOT / "eval/corpus")
    for doc_id, action in corpus.prepare(DOCUMENTS):
        print(f"{doc_id}: {action}", flush=True)
    by_file = {corpus.documents[doc_id].file: corpus.documents[doc_id] for doc_id in DOCUMENTS}

    out: Path = args.out
    shutil.rmtree(out, ignore_errors=True)
    (out / "pages").mkdir(parents=True)
    with tempfile.TemporaryDirectory() as data_dir:
        settings = load_settings(args.config).model_copy(update={"data_dir": Path(data_dir)})
        fonti = Fonti(settings)
        try:
            for result in fonti.ingest(corpus.path(doc_id) for doc_id in DOCUMENTS):
                print(f"indexed {result.path.name}", flush=True)
            groups = []
            number = 0
            for title, questions in QUESTIONS:
                items = []
                for question in questions:
                    number += 1
                    answer = fonti.ask(question)
                    items.append(_item(number, answer, fonti, by_file, out))
                    print(f"answered: {question}", flush=True)
                groups.append({"title": title, "items": items})
        finally:
            fonti.close()

    environment = Environment(loader=FileSystemLoader(HERE), autoescape=select_autoescape())
    page = environment.get_template("index.html.j2").render(
        groups=groups,
        documents=[corpus.documents[doc_id] for doc_id in DOCUMENTS],
        model=settings.llm.model,
        version=__version__,
        repo=REPO,
    )
    (out / "index.html").write_text(page, encoding="utf-8")
    shutil.copy(ROOT / "src/fonti/web/static/app.css", out / "app.css")
    shutil.copy(ROOT / "src/fonti/web/static/favicon.svg", out / "favicon.svg")
    shutil.copy(HERE / "README.md", out / "README.md")
    print(f"written: {out}")


def _item(
    number: int, answer: Answer, fonti: Fonti, by_file: dict[str, CorpusDocument], out: Path
) -> dict[str, Any]:
    anchor = f"d{number}"
    cards: dict[int, dict[str, Any]] = {}  # one card per cited source, as in the web UI
    for citation in answer.citations:
        card = cards.setdefault(
            citation.number,
            {
                "anchor": f"{anchor}-fonte-{citation.number}",
                "number": citation.number,
                "title": citation.title or citation.filename,
                "section": citation.section,
                "passages": [],
            },
        )
        card["passages"].append(
            {
                "page": citation.page,
                "text": citation.passage,
                "image": _page_image(
                    fonti, citation.doc_id, citation.page, citation.start, citation.end, out
                ),
                "source": _source_link(by_file[citation.filename], citation.page),
            }
        )
    nearest = [
        {
            "title": hit.title or hit.filename,
            "page": hit.page_start,
            "text": " ".join(hit.text.split())[:280],
        }
        for hit in (answer.sources if answer.abstained else ())
    ]
    return {
        "anchor": anchor,
        "question": answer.question,
        "abstained": answer.abstained,
        "text": answer.text if answer.abstained else _with_markers(answer.text, anchor),
        "citations": list(cards.values()),
        "nearest": nearest,
    }


def _with_markers(text: str, anchor: str) -> Markup:
    """Escape the answer, then turn its [n] markers into links to the citation cards.

    Bullets written by the model become "•"; the template keeps the line breaks."""
    text = _BULLET.sub("• ", text)

    def link(match: re.Match[str]) -> str:
        numbers = re.split(r"\s*[,;]\s*", match.group(1))
        return ",".join(f'<a class="marker" href="#{anchor}-fonte-{n}">{n}</a>' for n in numbers)

    linked = _MARKER.sub(link, str(escape(text)))
    # Adjacent markers ([1][2]) would read as one number (12).
    return Markup(linked.replace('</a><a class="marker"', '</a>,<a class="marker"'))


def _page_image(fonti: Fonti, doc_id: str, page: int, start: int, end: int, out: Path) -> str:
    name = f"pages/{doc_id[:12]}-{page}-{start}-{end}.png"
    path = fonti.stored_file(doc_id)
    text = fonti.store.document_text(doc_id) or ""
    assert path is not None
    (out / name).write_bytes(render_page(path, page, text[start:end], scale=1.3))
    return name


def _source_link(document: CorpusDocument, page: int) -> str:
    if document.url is not None:
        return f"{document.url}#page={page}"
    return f"{REPO}/blob/main/eval/corpus/{document.source}"


if __name__ == "__main__":
    main()
