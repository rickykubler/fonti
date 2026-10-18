# Changelog

## 0.1.1 (2026-10-18)

Fixes from an independent review of the code, the golden set and a hands-on demo test.

### Fixed

- Sentences that their cited source does not support lose the `[n]` marker, and citations
  are numbered without gaps; before, an unsupported sentence could look cited.
- Web UI: closing the page during a streamed answer no longer blocks later questions and
  uploads for minutes; an unexpected error during an upload marks the job as failed.
- Web UI: requests made by other sites' pages are refused (`Sec-Fetch-Site`,
  `Cross-Origin-Resource-Policy`); page previews say when a scanned page cannot be
  highlighted.
- `fonti doctor` reports a remote LLM also when `llm.allow_remote` is on.
- `fonti reindex` keeps the index flagged when a document cannot be rebuilt, instead of
  mixing vectors of two embedders; `fonti models pull` without the docling extra prints the
  usual message.
- PDF parsing: running headers that alternate between even and odd pages (Official Journal)
  are removed and dates are no longer read as section numbers; long metadata titles are
  shortened.
- CLI output is UTF-8 when piped or redirected.

### Evaluation

- Retrieved evidence counts only on the page of its quote and with the same numbers;
  groundedness judges every sentence on the passages of the sources it cites; five golden
  answers corrected against their source. Recall@1 0.80, recall@5 0.93, groundedness 0.90,
  correctness 0.97 on 75 questions (`2026-10-18_default_main`).
- OCR engines compared on the synthetic scans (EasyOCR stays the default; Tesseract with
  `tessdata_best` is better on running text but empties short table cells).
- `eval/configs/default.toml` spells out the shipped defaults.

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
  61% on the GDPR and AI Act questions, against 97% on the other documents; still open in
  0.1.1).
- OCR of dense justified text: EasyOCR interleaves adjacent lines (CER about 25% on the
  synthetic scan of the Constitution); answers on scans usually stay correct.
