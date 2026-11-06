---
title: fonti
emoji: 📚
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
short_description: Italian RAG demo with verifiable citations
---

# fonti — public demo

Read-only demo of [fonti](https://github.com/rickykubler/fonti), a local-first RAG system for
Italian documents: every answer cites document, page and the exact passage, copied from the
source, and says «Non lo so» when the documents are not enough.

The index holds eight public and synthetic documents (Costituzione, GDPR, AI Act, AgID
guidelines, an ISTAT release, a rental contract, a condominium meeting report and a boiler
manual). The example questions were answered at build time and show up instantly; your own
questions run live on a free 2-CPU machine with a small model (qwen3.5:4b), so they take one or
two minutes and are less accurate than the local setup (gemma4:12b on a GPU).

Docker Spaces need a Hugging Face PRO subscription, so the published demo is the static one
in `deploy/static`. This folder is the live Space: `Dockerfile` builds fonti, downloads the models and documents,
indexes them and precomputes the example answers; `start.sh` starts Ollama and the web UI.
