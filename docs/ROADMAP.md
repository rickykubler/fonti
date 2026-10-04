# Roadmap

Milestones are executed in order. Each step is verified (ruff, mypy, pytest) and committed on
`feat/v0.1`. Check boxes are updated as work lands.

## M0 — Skeleton

- [x] Repository, README, LICENSE (Apache-2.0), CLAUDE.md, this roadmap
- [x] Tooling: uv, ruff, mypy (strict), pytest, pre-commit, CI on Ubuntu and Windows

## M1 — End-to-end pipeline

- [x] Configuration (TOML + environment variables), domain types, SQLite store (FTS5, vectors, metadata)
- [x] Fast PDF parser (pypdfium2), text cleaning, structure-aware chunking with page offsets
- [x] Embedder (sentence-transformers, `BAAI/bge-m3`, fp16 on CUDA), exact vector search, BM25, RRF
- [x] LLM clients (Ollama native, OpenAI-compatible) with local-only guard, Italian prompt, citation
      alignment, abstention
- [x] CLI: `ingest`, `ask`, `docs`, `remove`, `reindex`, `models pull`
- [x] Cached models load with the Hub disabled: no network traffic after the first download

**Done when:** `fonti ask "Quando è ammessa la restrizione della libertà personale?"` cites Art. 13
of the Constitution with page and passage, and an out-of-corpus question returns "Non lo so".

**Result:** verified on the Quirinale edition of the Constitution (65 pages, 188 chunks, ingest
14 s on an RTX 5060 Ti): the answer cites Art. 13 on page 7 with two verbatim passages; "Chi ha
vinto i Mondiali di calcio del 2006?" returns "Non lo so" with the nearest passages.

## M2 — Quality and evaluation

- [ ] Italian BM25: stemming, stopwords, FTS5 query sanitization, legal abbreviation expansion
- [ ] Reranker (`BAAI/bge-reranker-v2-m3`) and relevance gate
- [ ] Docling parser (OCR, tables, DOCX), `auto` routing, header/footer removal, de-hyphenation
- [ ] Evaluation framework: dataset format, metrics, runner, reports
- [ ] Public corpus manifest and download script; synthetic documents and synthetic scans
- [ ] Golden set (~60 questions) with automatic evidence verification
- [ ] Baseline and comparisons: embedders, reranker on/off, LLMs, OCR engines; calibrated thresholds

**Done when:** a committed report compares against the baseline. Initial targets, to be revised after
the baseline:

| Metric | Target |
|---|---|
| Recall@5 | ≥ 0.85 |
| Correct refusals (unanswerable questions) | ≥ 80% |
| False refusals (answerable questions) | ≤ 10% |
| Groundedness | ≥ 0.90 |
| Cited page correct | ≥ 90% |
| CER on clean synthetic scans | ≤ 3% |

## M3 — Web UI and demo

- [ ] Ask page: streamed answer, citation cards, open PDF at page, page preview with highlighted passage
- [ ] Documents page: upload, background ingestion with status, delete; JSON API
- [ ] Security: loopback bind, Host/Origin checks, upload limits, files served by id only
- [ ] `fonti doctor` (checks Ollama, models, GPU)
- [ ] Demo screenshots

## M4 — Documentation and release preparation

- [ ] Full README, `docs/architecture.md`, `docs/evaluation.md`
- [ ] CONTRIBUTING, issue templates, CHANGELOG, NOTICE (model and data licenses)
- [ ] Clean install test from a fresh clone

## Needs the maintainer

- Merge to `main` and tag `v0.1.0`
- Create the GitHub repository and push
- Feedback from real testers
- Human review of the golden set and of ~20 LLM-judge verdicts

## Decision log

| Area | Decision | Why |
|---|---|---|
| Language | Python 3.12, uv | PDF/OCR/ML ecosystem; 3.12 is the safest target for torch and Docling |
| Orchestration | No RAG framework | Full control over citations and abstention, few dependencies |
| Storage | Single SQLite file: FTS5 + float32 vectors, exact search with numpy | No servers, one file to back up; exact search is fast enough up to ~100–200k chunks |
| Retrieval | BM25 + dense, RRF, cross-encoder reranker | Keyword search catches exact legal references that embeddings miss |
| Parsing | pypdfium2 (fast) + Docling (OCR, tables) behind one interface | Permissive licenses; Docling covers hard PDFs, the fast parser keeps CI light |
| LLM runtime | Ollama via the OpenAI-compatible API | Native on Windows with GPU; the same client works with other local servers |
| Web | FastAPI + Jinja2 + HTMX | Few dependencies, custom citation UI, no telemetry |
| License | Apache-2.0 | Permissive, with an explicit patent grant |
| Citations | LLM cites `[n]`; passages are aligned verbatim from the source by term overlap | Small local models paraphrase quotes; extracted passages always exist in the document |
| Model loading | Offline when cached (`HF_HUB_OFFLINE` set before import), explicit `models pull` | `local_files_only` alone still contacted the Hub on every run |

## Backlog (after v0.1)

- Multiple collections and conversation memory (follow-up questions)
- ANN backend (e.g. LanceDB) for corpora beyond ~200k chunks
- Native cloud-provider adapters with built-in citations (opt-in)
- Docker image; folder watching for automatic re-ingestion
