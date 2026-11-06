---
title: fonti
emoji: 📚
colorFrom: green
colorTo: blue
sdk: static
pinned: false
license: apache-2.0
short_description: Italian RAG demo with verifiable citations
---

# fonti — demo

Static demo of [fonti](https://github.com/rickykubler/fonti), a local-first RAG system for
Italian documents: every answer cites document, page and the exact passage, copied from the
source, and says «Non lo so» when the documents are not enough.

The answers were computed by fonti with its default configuration on seven public and
synthetic documents, then published as they came out. The page is built by
[`deploy/static/build.py`](https://github.com/rickykubler/fonti/tree/main/deploy/static).
