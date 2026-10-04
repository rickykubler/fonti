"""Command-line interface. Messages are Italian, like the rest of the user interface."""

import argparse
import io
import json
import logging
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict
from pathlib import Path

from fonti import __version__
from fonti.config import Settings, load_settings
from fonti.domain import Answer, Citation
from fonti.errors import FontiError
from fonti.generation.llm import is_loopback
from fonti.service import Fonti, IngestResult, IngestStatus

_STATUS_MARKS = {
    IngestStatus.ADDED: "+",
    IngestStatus.UPDATED: "~",
    IngestStatus.SKIPPED: "=",
    IngestStatus.FAILED: "!",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fonti",
        description="Fai domande ai tuoi documenti e ottieni risposte con citazioni verificabili.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--config", type=Path, help="file di configurazione TOML (predefinito: ./fonti.toml)"
    )
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="più dettagli (-vv per il debug)"
    )
    commands = parser.add_subparsers(dest="command", metavar="COMANDO")

    ingest = commands.add_parser("ingest", help="indicizza file o cartelle (PDF, TXT, MD)")
    ingest.add_argument("paths", nargs="+", type=Path, metavar="PERCORSO")

    ask = commands.add_parser("ask", help="fai una domanda sui documenti indicizzati")
    ask.add_argument("question", metavar="DOMANDA")
    ask.add_argument("--json", action="store_true", help="stampa la risposta in JSON")

    commands.add_parser("docs", help="elenca i documenti indicizzati")

    remove = commands.add_parser("remove", help="rimuove un documento dall'indice")
    remove.add_argument("doc_id", metavar="ID", help="id del documento (bastano i primi caratteri)")

    commands.add_parser("reindex", help="ricostruisce l'indice con la configurazione attuale")

    models = commands.add_parser("models", help="gestisce i modelli locali")
    models.add_argument(
        "action", choices=["pull"], help="pull: scarica i modelli configurati (serve la rete)"
    )

    commands.add_parser("doctor", help="controlla installazione, modelli e Ollama")

    serve = commands.add_parser("serve", help="avvia l'interfaccia web su questo computer")
    serve.add_argument("--port", type=int, help="porta (predefinita: web.port, 8000)")
    serve.add_argument("--open", action="store_true", help="apre il browser")

    evaluation = commands.add_parser("eval", help="valutazione su dataset di prova (sviluppo)")
    evaluation.add_argument("--eval-dir", type=Path, default=Path("eval"), help="cartella eval")
    actions = evaluation.add_subparsers(dest="eval_action", metavar="AZIONE", required=True)
    corpus = actions.add_parser("corpus", help="scarica e genera i documenti del corpus")
    corpus.add_argument("ids", nargs="*", metavar="ID", help="solo questi documenti")
    check = actions.add_parser("check", help="verifica le evidenze del dataset nei documenti")
    check.add_argument("--dataset", default="main")
    run = actions.add_parser("run", help="valuta la configurazione corrente su un dataset")
    run.add_argument("--dataset", default="main")
    run.add_argument("--label", default="run", help="nome del run, usato nel nome del report")
    run.add_argument("--retrieval-only", action="store_true", help="niente LLM: solo retrieval")
    run.add_argument("--no-judge", action="store_true", help="niente giudice LLM")
    run.add_argument("--judge-model", help="modello del giudice (predefinito: llm.model)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    levels = [logging.WARNING, logging.INFO, logging.DEBUG]
    logging.basicConfig(
        level=levels[min(args.verbose, 2)], format="%(levelname)s %(name)s: %(message)s"
    )
    _tolerate_unencodable_output()
    try:
        settings = load_settings(args.config)
        if args.command == "eval":
            return _evaluate(settings, args)
        if args.command == "serve":
            return _serve(settings, args)
        if args.command == "doctor":
            return _doctor(settings)
        with Fonti(settings) as fonti:
            return _COMMANDS[args.command](fonti, args)
    except FontiError as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 1


def _ingest(fonti: Fonti, args: argparse.Namespace) -> int:
    return _report(fonti.ingest(args.paths))


def _reindex(fonti: Fonti, args: argparse.Namespace) -> int:
    return _report(fonti.reindex())


def _report(results: Iterable[IngestResult]) -> int:
    failed = 0
    for result in results:
        detail = f"{result.chunks} chunk" if result.chunks else result.message
        print(f"{_STATUS_MARKS[result.status]} {result.path.name}: {detail}", flush=True)
        failed += result.status is IngestStatus.FAILED
    return 1 if failed else 0


def _ask(fonti: Fonti, args: argparse.Namespace) -> int:
    answer = fonti.ask(args.question)
    if args.json:
        print(json.dumps(asdict(answer), ensure_ascii=False, indent=2))
    else:
        _print_answer(answer)
    return 0


def _docs(fonti: Fonti, args: argparse.Namespace) -> int:
    documents = fonti.documents()
    if not documents:
        print("Nessun documento indicizzato. Usa `fonti ingest PERCORSO`.")
        return 0
    for doc in documents:
        title = f" — {doc.title}" if doc.title else ""
        sizes = f"{doc.page_count:>4} pag.  {doc.chunk_count:>5} chunk"
        print(f"{doc.id[:12]}  {sizes}  {doc.filename}{title}")
    return 0


def _remove(fonti: Fonti, args: argparse.Namespace) -> int:
    info = fonti.remove(args.doc_id)
    print(f"Rimosso {info.filename} ({info.id[:12]})")
    return 0


def _doctor(settings: Settings) -> int:
    from fonti.doctor import Status, run_checks

    checks = run_checks(settings)
    width = max(len(check.name) for check in checks)
    for check in checks:
        print(f"[{check.status.value}] {check.name:<{width}}  {check.detail}")
    return 1 if any(check.status is Status.FAILED for check in checks) else 0


def _serve(settings: Settings, args: argparse.Namespace) -> int:
    import threading
    import webbrowser

    import uvicorn

    from fonti.web.app import create_app

    host, port = settings.web.host, args.port or settings.web.port
    if not is_loopback(host):
        print(
            f"Errore: web.host = {host} esporrebbe documenti e domande sulla rete. "
            "L'interfaccia ascolta solo su questo computer (127.0.0.1).",
            file=sys.stderr,
        )
        return 1
    url = f"http://{host}:{port}/"
    print(f"fonti è in ascolto su {url} (Ctrl+C per fermarlo)", flush=True)
    if args.open:
        threading.Timer(1.5, webbrowser.open, args=(url,)).start()
    uvicorn.run(create_app(settings), host=host, port=port, log_level="warning")
    return 0


def _evaluate(settings: Settings, args: argparse.Namespace) -> int:
    # Imported here: evaluation needs the development dependencies.
    from fonti.evaluation.corpus import Corpus
    from fonti.evaluation.dataset import check_dataset, load_dataset
    from fonti.evaluation.judge import Judge
    from fonti.evaluation.report import write_report
    from fonti.evaluation.runner import run
    from fonti.generation.llm import create_chat_client

    corpus = Corpus(args.eval_dir / "corpus")
    if args.eval_action == "corpus":
        for doc_id, action in corpus.prepare(args.ids or None):
            print(f"{doc_id}: {action}", flush=True)
        return 0
    dataset = load_dataset(args.eval_dir / "datasets", args.dataset)
    if args.eval_action == "check":
        problems = check_dataset(dataset, corpus)
        for problem in problems:
            print(problem)
        print(f"{len(dataset.questions)} domande, {len(problems)} problemi")
        return 1 if problems else 0
    judge = None
    if not args.retrieval_only and not args.no_judge:
        judge_llm = settings.llm
        if args.judge_model:
            judge_llm = judge_llm.model_copy(update={"model": args.judge_model})
        judge = Judge(create_chat_client(judge_llm))
    result = run(
        dataset,
        corpus,
        settings,
        work_dir=args.eval_dir / ".work",
        label=args.label,
        generate=not args.retrieval_only,
        judge=judge,
        progress=lambda message: print(message, file=sys.stderr, flush=True),
    )
    markdown, _ = write_report(result, args.eval_dir / "reports")
    for key, value in result.summary().items():
        print(f"{key:>20}: {'—' if value is None else round(value, 3)}")
    print(f"Report: {markdown}")
    return 0


def _models(fonti: Fonti, args: argparse.Namespace) -> int:
    for path in fonti.pull_models():
        print(f"Modello pronto: {path}")
    return 0


_COMMANDS: dict[str, Callable[[Fonti, argparse.Namespace], int]] = {
    "ingest": _ingest,
    "ask": _ask,
    "docs": _docs,
    "remove": _remove,
    "reindex": _reindex,
    "models": _models,
}


def _print_answer(answer: Answer) -> None:
    print(answer.text)
    if answer.citations:
        print("\nFonti:")
        by_source: dict[int, list[Citation]] = {}
        for citation in answer.citations:
            by_source.setdefault(citation.number, []).append(citation)
        for number, citations in by_source.items():
            first = citations[0]
            section = f" — {first.section}" if first.section else ""
            print(f"[{number}] {first.title or first.filename}{section}")
            for citation in citations:
                print(f"    pag. {citation.page}: «{_shorten(citation.passage)}»")
    elif answer.sources:
        print("\nPassaggi più vicini trovati (non bastano per rispondere):")
        for hit in answer.sources:
            print(f"- {hit.filename}, pag. {hit.page_start}: «{_shorten(hit.text, 160)}»")


def _shorten(text: str, limit: int = 300) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def _tolerate_unencodable_output() -> None:
    """Replace characters the console encoding cannot show instead of crashing."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="replace")
