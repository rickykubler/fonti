---
paths:
  - "src/fonti/ingest/**"
  - "src/fonti/index/**"
  - "src/fonti/ml/**"
  - "src/fonti/retrieval/**"
  - "src/fonti/generation/**"
  - "src/fonti/config.py"
  - "eval/configs/**"
---

# Answer-quality changes

Changes here can move retrieval or answer quality. Tests passing is not enough:

- Compare against a baseline eval on the same dataset before calling the change done
  (skill `eval-compare`). Report metric deltas, including regressions.
- Retrieval-only changes (chunking, BM25, dense, fusion, rerank): `--retrieval-only` is enough.
  Prompt, citation or LLM changes need a full run.
- Latency numbers depend on GPU load: check `nvidia-smi` before trusting `*_p50_s`/`*_p95_s`.
- Never tune against the eval by editing golden answers or evidence.
