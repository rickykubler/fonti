# Changelog

## 0.1.0 (unreleased)

First version: ask questions about your documents in Italian, locally, with verified citations.

### Features

- Ingestion of PDF (text layer, or Docling with EasyOCR for scanned pages), DOCX, TXT and
  Markdown; Italian legal structure (Parte, Titolo, Capo, Sezione, Art.), running headers
  removed, tables kept as Markdown.
- One SQLite file per collection: documents, pages, chunks, FTS5 keyword index and vectors;
  a content-addressed copy of every file.
- Hybrid retrieval: BM25 with Italian stems and expanded legal abbreviations, dense search,
  RRF fusion, cross-encoder reranking and a relevance gate.
- Answers from a local LLM through Ollama (or any OpenAI-compatible server, opt-in for remote
  ones) with `[n]` citations; passages copied verbatim from the source with their page;
  «Non lo so» when evidence is missing.
- CLI: `ingest`, `ask`, `docs`, `remove`, `reindex`, `models pull`, `doctor`, `serve`, `eval`.
- Local web UI: streamed answers, citation cards, PDF opened at the cited page, page preview
  with the passage highlighted, upload with background indexing.
- Evaluation framework: corpus manifest, synthetic documents and scans, 59-question golden
  set, retrieval and answer metrics, LLM judge, Markdown/JSON reports.

### Privacy

- Remote LLM endpoints and Ollama cloud models refused unless `llm.allow_remote = true`.
- Models load offline once downloaded; Hugging Face telemetry disabled.
- Web UI bound to 127.0.0.1 with Host and Origin checks.
