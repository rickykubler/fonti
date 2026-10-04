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

- [x] Italian BM25: Snowball stemming, stopwords, FTS5 query sanitization
- [x] Legal abbreviation expansion ("d.lgs." ↔ "decreto legislativo")
- [x] Reranker (`BAAI/bge-reranker-v2-m3`) and relevance gate (min_score 0.1)
- [x] Docling parser (OCR, tables, DOCX), `auto` routing, running header/footer removal
- [x] Evaluation framework: dataset format, metrics, LLM judge, runner, Markdown/JSON reports
- [x] Public corpus manifest, downloader, synthetic documents and synthetic scans
- [x] Golden set: 59 questions (47 answerable, 12 not) with automatic evidence verification
- [x] Baseline and ablations: stemming, reranker, gate, Docling on digital PDFs, OCR on scans
- [ ] GDPR and AI Act in the corpus: EUR-Lex blocks automated downloads (HTTP 202); download
      the PDFs by hand into `eval/corpus/files/`, record their SHA-256, add questions
- [x] Embedder comparison: granite R2, Qwen3-Embedding-0.6B and bge-m3 are equivalent with the
      reranker; granite R2 is the default (faster, smaller)
- [ ] LLM comparison: `gemma4:12b`, `qwen3.5:9b` vs `qwen2.5:14b` (full runs, `llm.think = false`)
- [x] OCR engines on scans: EasyOCR (default) vs RapidOCR latin; see docs/evaluation.md
- [ ] OCR reading order on justified multi-line text: EasyOCR interleaves adjacent lines (CER
      ~25% on the Constitution scan); RapidOCR keeps the order but drops accents: an
      accent-aware Latin recognition model or a post-OCR line re-ordering is still to try

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

**Results** (`eval/reports/`, main dataset, qwen2.5:14b):

| Run | Recall@1 | Recall@5 | MRR@10 | Correct refusals | False refusals | Cited pages | Groundedness |
|---|---|---|---|---|---|---|---|
| baseline (M1) | 0.808 | 0.957 | 0.873 | 0.83 | 0.00 | 0.90 | 0.88 |
| + stemming, reranker, gate, generation fixes | 0.947 | 0.979 | 0.966 | 1.00 | 0.02 | 0.96 | 0.92 |

Scans (Docling + EasyOCR): correctness 0.94, cited pages 1.0, recall@5 0.80 (OCR noise lowers
quote matching), ingest 1.5 s/page. Known failure: cost-08 answers with the historical text of
Art. 56 quoted in the notes instead of the current one.

## M3 — Web UI and demo

- [x] Ask page: streamed answer, citation cards, open PDF at page, page preview with highlighted passage
- [x] Documents page: upload, background ingestion with status, delete; JSON API (`/api/ask`, `/api/ask/stream`)
- [x] Security: loopback only, Host/Origin checks, upload limits, files served by id only
- [ ] Manual check in a browser (`uv run fonti serve --open`)
- [x] `fonti doctor` (checks Ollama, models, GPU)
- [ ] Demo screenshots

## M4 — Documentation and release preparation

- [x] Full README, `docs/architecture.md`, `docs/evaluation.md`
- [x] CONTRIBUTING, issue templates, CHANGELOG, NOTICE (model and data licenses)
- [x] Clean install test from a fresh clone (`uv sync --extra cpu`, 164 tests passing)

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
| Embedder | `ibm-granite/granite-embedding-311m-multilingual-r2` | Same recall as bge-m3 with the reranker, 38% faster ingest, smaller download |
| Parser | `auto`: text layer, Docling only for scanned pages | Docling gave no gain on digital PDFs at 0.5 s/page |
| Model loading | Offline when cached (`HF_HUB_OFFLINE` set before import), explicit `models pull` | `local_files_only` alone still contacted the Hub on every run |

## Backlog (after v0.1)

- Multiple collections and conversation memory (follow-up questions)
- ANN backend (e.g. LanceDB) for corpora beyond ~200k chunks
- Native cloud-provider adapters with built-in citations (opt-in)
- Docker image; folder watching for automatic re-ingestion
