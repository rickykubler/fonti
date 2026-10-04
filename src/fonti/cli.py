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
from fonti.config import load_settings
from fonti.domain import Answer
from fonti.errors import FontiError
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


_COMMANDS: dict[str, Callable[[Fonti, argparse.Namespace], int]] = {
    "ingest": _ingest,
    "ask": _ask,
    "docs": _docs,
    "remove": _remove,
    "reindex": _reindex,
}


def _print_answer(answer: Answer) -> None:
    print(answer.text)
    if answer.citations:
        print("\nFonti:")
        for citation in answer.citations:
            where = f"pag. {citation.page}"
            if citation.section:
                where += f", {citation.section}"
            print(f"[{citation.number}] {citation.title or citation.filename} ({where})")
            print(f"    «{_shorten(citation.passage)}»")
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
