# fonti

**Ask questions about your own documents — in Italian, on your machine, with sources you can check.**

> **In italiano.** *fonti* è un sistema RAG open source per fare domande sui propri documenti in italiano: contratti, normative, verbali, manuali. Gira interamente in locale per impostazione predefinita, gestisce PDF difficili, scansioni e tabelle, e ogni risposta riporta documento, pagina e passaggio esatto. Se le fonti non bastano, risponde che non lo sa invece di inventare.

**Status: pre-alpha, under active development.** Progress is tracked in [docs/ROADMAP.md](docs/ROADMAP.md).

## Why

- **Italian first.** Tuned and evaluated on Italian documents: legal references ("art. 1341 c.c.", "D.Lgs. 196/2003"), accents and apostrophes, hyphenated line breaks, scanned pages and tables.
- **Local-first.** Embeddings, reranking and the LLM run on your machine (the LLM through [Ollama](https://ollama.com)). Nothing is sent to external services by default; cloud providers are opt-in.
- **Verifiable citations.** Every answer cites document, page and the exact passage, copied from the source rather than generated. When the sources are not enough, the answer is "non lo so".
- **Measured, not guessed.** A small evaluation framework (retrieval recall@k and MRR, abstention, citation accuracy, groundedness) drives every default.

## How it works

1. **Ingest:** parse PDFs (including OCR for scans), clean the text, split it into chunks that follow the document structure (titles, articles, sections) and keep page offsets.
2. **Index:** store everything in a single SQLite file — text, a BM25 keyword index (FTS5) and the embedding vectors.
3. **Retrieve:** hybrid search (keywords + semantic), rank fusion, then a multilingual reranker.
4. **Answer:** a local LLM answers in Italian using only the retrieved sources and cites them; citations are checked mechanically and the system abstains when evidence is missing.

## Getting started (development)

Requirements: Windows, Linux or macOS and [uv](https://docs.astral.sh/uv/). Ollama is needed for answers.

```
uv sync
uv run pytest
uv run fonti --version
```

## License

[Apache-2.0](LICENSE).
