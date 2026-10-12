---
name: eval-compare
description: Measure the effect of a change on fonti retrieval/answer quality by comparing two eval runs (baseline vs candidate) and reporting metric deltas. Use after changing ingest, chunking, retrieval, reranking, prompts, citations or models.
---

# Eval compare

## 1. Pick the runs

- Same `--dataset` (default `main`) and same mode for both runs: both `--retrieval-only`, or both full.
- Baseline: prefer an existing report in `eval/reports/` whose settings differ only by the
  change. Otherwise run the baseline before applying the change (ask before stashing or
  switching branches).
- Check `nvidia-smi` first if latency matters; note GPU load in the report.

## 2. Run

```
uv run fonti eval check --dataset main
uv run fonti --config eval/configs/<name>.toml eval run --dataset main --label <label> --retrieval-only
```

Drop `--retrieval-only` for prompt, citation or LLM changes. Each run writes
`eval/reports/<date>_<label>_<dataset>.{md,json}`.

## 3. Compare

```
uv run python .claude/skills/eval-compare/compare.py <baseline.json> <candidate.json>
```

The script prints every metric in `summary` with the delta and marks regressions.

## Report

- The delta table (from the script).
- Verdict in one line: improves, neutral, or regresses (name the metrics).
- Settings that differ between the two runs (the script lists them).
- Questions that flipped outcome if the change is a regression: compare `questions` in the JSONs.
