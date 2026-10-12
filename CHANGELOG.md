# Changelog

## 0.1.0 (2026-10-12)

First version: ask questions about your documents in Italian, locally, with verified citations.

### Features

- Ingestion of PDF (text layer, or Docling with EasyOCR for scanned pages), DOCX, TXT and
  Markdown; Italian legal structure (Parte, Titolo, Capo, Sezione, Art.), running headers
  removed, tables kept as Markdown.
- One SQLite file per collection: documents, pages, chunks, FTS5 keyword index and vectors;
  a content-addressed copy of every file.
- Hybrid retrieval: BM25 with Italian stems and expanded legal abbreviations, dense search,
  RRF fusion, cross-encoder reranking and a relevance gate.
- Answers from a local LLM through Ollama (default `gemma4:12b`, chosen on the golden set; or
  any OpenAI-compatible server, opt-in for remote ones) with `[n]` citations; passages copied
  verbatim from the source with their page; «Non lo so» when evidence is missing.
- CLI: `ingest`, `ask`, `docs`, `remove`, `reindex`, `models pull`, `doctor`, `serve`, `eval`.
- Local web UI: streamed answers, citation cards, PDF opened at the cited page, page preview
  with the passage highlighted, upload with background indexing.
- Evaluation framework: corpus manifest, synthetic documents and scans, 75-question golden
  set (including GDPR and AI Act), retrieval and answer metrics, LLM judge, Markdown/JSON
  reports.

### Privacy

- Remote LLM endpoints and Ollama cloud models refused unless `llm.allow_remote = true`.
- Models load offline once downloaded; Hugging Face telemetry disabled.
- Web UI bound to 127.0.0.1 with Host and Origin checks.

### Known limitations

- On EU regulations answers often cite a recital instead of the article (cited pages correct
  61% on the GDPR and AI Act questions, against 97% on the other documents).
- OCR of dense justified text: EasyOCR interleaves adjacent lines (CER about 25% on the
  synthetic scan of the Constitution); answers on scans usually stay correct.
