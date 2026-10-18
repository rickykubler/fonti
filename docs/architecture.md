# Architecture

fonti is a small Python package (about 3,000 lines without tests and the evaluation code) with no RAG framework: every
step is plain code that can be read and tested on its own. This page explains how a document
becomes searchable and how a question becomes a cited answer.

## Overview

```
                 ingest                                          ask
file ──► parse ──► clean ──► chunk ──► embed ──► SQLite ◄── retrieve ◄── question
         (fast │ Docling)    (sections, (granite R2)│ documents          │ BM25 + dense
                             offsets)              │ pages              │ RRF fusion
                                                   │ chunks             │ reranker
                                                   │ FTS5 (BM25)        │ gate
                                                   │ vectors            ▼
                                                   └────────────► LLM (Ollama) ──► citations
                                                                   [n] markers     verified
                                                                                   or "Non lo so"
```

`service.Fonti` is the only entry point: the CLI (`cli.py`), the web UI (`web/`) and the
evaluation runner (`evaluation/`) all go through `ingest()`, `retrieve()`, `answer()` and
`ask()`.

## Modules

| Module | Responsibility |
|---|---|
| `config.py` | Settings: code defaults < `fonti.toml` < `.env` < `FONTI_*` variables |
| `domain.py` | Dataclasses shared by all layers (`Block`, `Chunk`, `Hit`, `Citation`, `Answer`, …) |
| `italian.py` | Italian stopwords, accent folding, Snowball stemming |
| `ingest/parsers.py` | Fast PDF parser (pypdfium2 text layer), text/Markdown parser, running headers |
| `ingest/docling_parser.py` | Docling: layout, reading order, tables, OCR of scanned regions, DOCX |
| `ingest/structure.py` | Headings of Italian legal documents (Parte, Titolo, Capo, Sezione, Art.), paragraphs |
| `ingest/chunking.py` | Structure-aware chunks that are exact slices of the document text |
| `index/store.py` | SQLite schema and all SQL: documents, pages, chunks, FTS5, vectors, settings |
| `index/text.py` | BM25 terms (stems, expanded legal abbreviations) and FTS5 query building |
| `index/vectors.py` | Exact cosine search over the stored vectors with numpy |
| `ml/` | sentence-transformers embedder and cross-encoder reranker; cache-first model loading |
| `retrieval/hybrid.py` | BM25 and dense rankings fused with Reciprocal Rank Fusion |
| `generation/llm.py` | Ollama and OpenAI-compatible clients; refuses non-local endpoints by default |
| `generation/prompts.py` | The Italian system prompt and the numbered sources |
| `generation/citations.py` | Parses `[n]` markers, aligns verbatim passages, detects refusals |
| `web/` | FastAPI app, Jinja2 templates, HTMX, background ingestion, page previews |
| `evaluation/` | Corpus, golden dataset, metrics, LLM judge, runner, reports |
| `doctor.py` | Environment checks for `fonti doctor` |

## Ingestion

1. **Identity.** A document is identified by the SHA-256 of its file. A copy is kept in
   `<data_dir>/files/<sha256>.<ext>`, so a citation always points to the exact version that
   was indexed, and indexing the same file twice does nothing.
2. **Parsing.** In `auto` mode the PDF text layer is read with pypdfium2; pages without text
   (scans) send the document to Docling, which runs layout analysis and EasyOCR. Page numbers,
   footnote marks glued to headings and running headers/footers are removed; NFKC
   normalization fixes ligatures; PDFium hyphenation marks are dropped.
3. **Structure.** Lines become heading and paragraph blocks. Italian legal headings are
   recognized with their depth (Parte 1 › Titolo 2 › Capo 3 › Sezione 4 › Art. 5), including
   letter-spaced ones ("P A R T E I") and titles on the following line ("Articolo 17" +
   "Diritto alla cancellazione").
4. **Chunking.** Blocks are grouped by heading path and packed into chunks of at most
   1,500 characters; longer blocks are split by sentences with an overlap. Tables are never
   mixed with prose and repeat their header in the indexed context when split. Every chunk
   keeps its document-level character offsets; pages are derived from offsets, so a chunk that
   spans two pages, or a passage inside it, always maps to the right page.
5. **Indexing.** The text indexed for a chunk is its heading path plus its text. It is
   embedded (granite-embedding-311m-multilingual-r2, float16 on CUDA) and its Italian keyword terms go to an FTS5 table. One
   SQLite transaction stores the document, its pages, chunks, terms and vectors. The settings
   that define the index (embedder, chunker, parser and keyword versions) are recorded: a
   mismatch stops queries and ingestion with "esegui `fonti reindex`".

## Answering

1. **Retrieval.** BM25 (FTS5, stemmed terms, every word ORed and quoted so that FTS5 syntax
   typed by users is inert) and dense search (exact cosine over all vectors) each return 50
   candidates, fused with RRF (k = 60). The top 30 are rescored by the cross-encoder
   bge-reranker-v2-m3.
2. **Gate.** If the best reranker score is below 0.1 the answer is "Non lo so" and the LLM
   is not called.
3. **Generation.** The six best passages are numbered in the prompt with document, page and
   section. The model (Ollama by default) must answer in Italian, put `[n]` after every
   sentence, write `NON_TROVATO` when the sources are not enough and treat sources as data, not
   instructions.
4. **Citations.** For every answer sentence and every source it cites, the supporting passage
   is the sentence of the source (extended to a neighbour when that covers more of the claim)
   that best matches it by stemmed term overlap and embedding similarity. Passages are copied
   from the document, never generated, and their page comes from the offsets. A citation
   counts only if the passage contains at least 30% of the claim's content words. Answers
   without any supported citation, `NON_TROVATO` and soft refusals ("Le fonti non
   specificano…") become "Non lo so", shown together with the nearest passages.

## Privacy

- The LLM client refuses non-loopback endpoints and Ollama cloud models unless
  `llm.allow_remote = true`.
- Models are downloaded once (`fonti models pull`); afterwards Hugging Face libraries are
  imported with `HF_HUB_OFFLINE=1`, because `local_files_only` alone still contacted the Hub.
  Telemetry of Hugging Face libraries is disabled.
- The web UI listens on 127.0.0.1 only, rejects other `Host` headers (DNS rebinding) and
  cross-origin writes (CSRF), and serves files by id only.
- Questions and document text are logged only at DEBUG level.
- The test suite blocks every non-loopback network connection.

## Storage

One SQLite file, `<data_dir>/index.sqlite3`, in WAL mode:

| Table | Content |
|---|---|
| `documents` | id (SHA-256), file name, title, suffix, pages, parser, full text, date |
| `pages` | character range of every page in the document text |
| `chunks` | offsets, pages, heading path, kind (text/table), exact text, indexed context |
| `chunks_fts` | FTS5 table with the keyword terms (unicode61, diacritics removed) |
| `embeddings` | one float32 vector per chunk |
| `meta` | schema version, index settings, revision counter (refreshes the vector cache) |

Vector search is exact: fast enough for personal collections (tens of milliseconds up to
about 100–200 thousand chunks). Beyond that, an approximate index such as LanceDB can replace
`index/vectors.py`.
