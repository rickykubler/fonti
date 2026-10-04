# Contributing

Thanks for helping! fonti is a small, personal, non-commercial project: issues with
questions that got a wrong answer are as valuable as code.

## Reporting a wrong answer

Use the "Risposta sbagliata" issue template. Please include the question, the answer, what
you expected and, if the document is public, where to get it. Never attach private documents:
describe the problem with a public or invented text instead.

## Development setup

Requirements: [uv](https://docs.astral.sh/uv/) and, for answers, [Ollama](https://ollama.com).

```
uv sync --extra cpu            # or --extra gpu with an NVIDIA GPU; add --extra docling for OCR
uv run pre-commit install
uv run pytest                  # fast tests, no network, no GPU: what CI runs
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -m slow          # real models, Docling, Ollama: run `fonti models pull` first
```

On Windows PowerShell 5.1 run the commands one per line (`&&` is not supported).

## Conventions

- Code, comments, commit messages and technical docs are in English; user-facing strings and
  LLM prompts are in Italian.
- Type hints everywhere (`mypy --strict`), `ruff` for lint and format, `pytest` for tests.
- `service.Fonti` is the only API used by the CLI, the web UI and the evaluation.
- All SQL lives in `index/store.py`. Chunks keep document-level offsets; pages come from
  offsets. Citation passages are copied from the documents, never generated.
- Network access only happens in the LLM client (loopback unless `allow_remote`) and when
  downloading models. Tests must not need the network or a GPU: use `HashingEmbedder` and
  `tests/fakes.py`, and mark tests that need real models with `@pytest.mark.slow`.
- Windows first: use `pathlib`, write tooling in Python, not shell scripts.
- Dependencies: justify every new one. No AGPL/GPL libraries (PyMuPDF, Marker, MinerU, Surya)
  and no libraries with telemetry on by default.
- Small commits with an imperative subject ("Add X", "Fix Y").

## Changing the quality of answers

Every change to parsing, chunking, retrieval or prompts must be measured:

```
uv run fonti eval corpus
uv run fonti eval check
uv run fonti --config eval/configs/rerank-gate.toml eval run --dataset main --label my-change
```

Compare the new report in `eval/reports/` with the latest one and commit both the change and
the report. Never edit the golden answers or evidence to make a run look better: if a gold
answer is wrong, fix it in a separate commit that explains why. See
[docs/evaluation.md](docs/evaluation.md).
