# Evaluation

Every default in fonti was chosen by measuring it on a golden dataset of Italian questions.
This page explains the corpus, the dataset, the metrics and how to run and extend them.

## Corpus

Defined in [`eval/corpus/manifest.toml`](../eval/corpus/manifest.toml) and built with
`uv run fonti eval corpus` into `eval/corpus/files/` (not committed):

| Id | Document | Kind | Source and license |
|---|---|---|---|
| `costituzione` | Costituzione della Repubblica Italiana, edition with notes (65 pages) | legislation | Presidenza della Repubblica; official act, no copyright (art. 5 L. 633/1941) |
| `agid` | AgID, Linee guida sul documento informatico (40 pages) | guidelines | AgID; act of a public administration |
| `istat` | ISTAT, Occupati e disoccupati, luglio 2026 (16 pages, many tables) | statistics | ISTAT, CC BY 4.0 |
| `contratto` | Lease agreement | contract | synthetic (CC0), rendered from Markdown |
| `verbale` | Condominium meeting minutes with a vote table | minutes | synthetic (CC0) |
| `manuale` | Boiler manual with technical and error-code tables | manual | synthetic (CC0) |
| `*-scan` | Synthetic scans of the Constitution, the contract and the manual | scans | derived: 200 dpi, grey, ±0.8° skew, blur, noise, JPEG |
| `gdpr`, `ai-act` | Regulations (EU) 2016/679 and 2024/1689 in Italian | legislation | EUR-Lex; not in the datasets yet, see below |

Downloads are checked against their SHA-256. EUR-Lex answers automated requests with an
empty HTTP 202, so the two regulations must currently be downloaded by hand into
`eval/corpus/files/` (`gdpr.pdf`, `ai_act.pdf`).

Synthetic scans have an exact ground truth (the text of the original), so OCR quality can be
measured as a character error rate (CER).

## Dataset

[`eval/datasets/questions.jsonl`](../eval/datasets/questions.jsonl) holds 59 questions: 47
answerable and 12 that the corpus cannot answer, several of them near misses ("Qual era il
tasso di disoccupazione in Germania?"). Each answerable question has a short expected answer
and its evidence: document, page and a verbatim quote, plus alternative locations when the
same fact appears in the text and in a table:

```json
{"id": "istat-01", "question": "Qual è il tasso di disoccupazione in Italia a luglio 2026?",
 "answerable": true, "answer": "5,8%, in calo di 0,1 punti.",
 "evidence": [{"doc": "istat", "page": 1, "quote": "Il tasso di disoccupazione scende al 5,8% (-0,1 punti)",
               "alternatives": [{"doc": "istat", "page": 3, "quote": "Tasso di disoccupazione 5,8"}]}],
 "tags": ["tabelle"]}
```

Evidence is identified by quote, never by chunk id, so the same questions keep working when
parsing or chunking change. `uv run fonti eval check` verifies that every quote is on its page.

Datasets are TOML files that select documents and questions: `main` (digital documents) and
`scans` (the same questions on the synthetic scans, through `aliases`).

## Metrics

Retrieval (answerable questions):

- **Recall@k**: share of evidence found in the first k results. A result contains an evidence
  when it is from the right document and contains the quote (fuzzy match ≥ 90, which absorbs
  OCR noise and table formatting).
- **MRR@10**: mean of 1/rank of the first result with evidence.

Answers:

- **Correct refusals**: share of unanswerable questions answered with "Non lo so".
- **False refusals**: share of answerable questions answered with "Non lo so".
- **Cited pages**: share of citations on a page that holds gold evidence.
- **Cites evidence**: share of answers with at least one cited passage overlapping a gold quote.
- **Groundedness** (LLM judge): for every answer sentence, are its cited passages enough to
  support it? Sentences without citations score 0.
- **Correctness** (LLM judge): does the answer contain the expected answer?
- Latencies (p50/p95) of retrieval and generation, ingestion seconds per page.

The judge is an LLM and can be wrong: keep it fixed when comparing runs
(`--judge-model qwen2.5:14b`) and check a sample of its verdicts by hand. With 47 answerable
questions each one is worth about 2 points of recall: differences below 5 points are noise.

## Running

```
uv run fonti eval corpus
uv run fonti eval check
uv run fonti --config eval/configs/rerank-gate.toml eval run --dataset main --label my-run
uv run fonti --config eval/configs/rerank-gate.toml eval run --dataset main --label quick --retrieval-only
```

Configurations live in [`eval/configs/`](../eval/configs/). Indexes are cached in `eval/.work/`
by the settings that define them, so runs that change only retrieval or generation reuse them.
Reports (Markdown and JSON) go to [`eval/reports/`](../eval/reports/) and are committed.

## Results

Main dataset, judge qwen2.5:14b; answering model qwen2.5:14b except in the last row.

| Run | Recall@1 | Recall@5 | MRR@10 | Correct refusals | False refusals | Cited pages | Groundedness | Correctness |
|---|---|---|---|---|---|---|---|---|
| Baseline: plain BM25 + bge-m3, no reranker | 0.808 | 0.957 | 0.873 | 0.83 | 0.00 | 0.90 | 0.88 | 0.94 |
| + Italian stemming (retrieval only) | 0.851 | 0.979 | 0.903 | | | | | |
| + reranker, gate 0.1, refusal and citation fixes | 0.947 | 0.979 | 0.966 | 1.00 | 0.02 | 0.96 | 0.92 | 0.96 |
| **Defaults**: granite R2, gemma4:12b (thinking off), parser `auto` | 0.947 | 0.979 | 0.966 | 1.00 | 0.02 | 0.97 | 0.90 | 0.98 |

Answering models, with the same retrieval (bge-m3, reranker, gate), thinking off and the same
judge (qwen2.5:14b):

| Model (Ollama, Q4_K_M) | Correct refusals | False refusals | Cited pages | Cites evidence | Groundedness | Correctness | Generation p50 / p95 (s) |
|---|---|---|---|---|---|---|---|
| qwen2.5:14b | 1.00 | 0.00 | 0.96 | 0.96 | 0.89 | 0.95 | 7.9 / 25.7 |
| **gemma4:12b** (default) | 1.00 | 0.02 | 0.97 | 1.00 | 0.91 | 0.98 | 3.5 / 7.3 |
| qwen3.5:9b | 0.92 | 0.02 | 0.91 | 0.93 | 0.82 | 0.96 | 3.0 / 8.4 |

gemma4:12b has the best groundedness and correctness, cites gold evidence in every answer and
is the only model that answers cost-08 with the current text of Art. 56 (400 deputies) instead
of the historical text quoted in the notes; like qwen3.5:9b, it refuses one answerable table
question (istat-05). qwen3.5:9b also answers an unanswerable question with an evasive sentence,
and its sentences are less often supported by their citations. The three runs ran while
another application was using the GPU, so their latencies are higher than the earlier
qwen2.5:14b run (p50 2.4 s) and are comparable only with each other. Thinking models need
`llm.think = false` (the default): otherwise Ollama lets them reason before answering, which
is slower and spends the answer's token budget (`llm.max_answer_tokens`).

Retrieval ablations (retrieval only):

| Variant | Recall@1 | Recall@5 | MRR@10 | Ingest (s, 130 pages, GPU) |
|---|---|---|---|---|
| bge-m3, no reranker | 0.851 | 0.979 | 0.903 | 47 |
| granite-embedding-311m-multilingual-r2, no reranker | 0.883 | 0.979 | 0.926 | 29 |
| Qwen3-Embedding-0.6B, no reranker | 0.830 | 0.957 | 0.890 | 30 |
| bge-m3 + reranker | 0.947 | 0.979 | 0.966 | |
| granite R2 + reranker | 0.947 | 0.979 | 0.966 | |
| Qwen3-Embedding-0.6B + reranker | 0.947 | 0.979 | 0.966 | |
| Docling instead of the text layer (digital PDFs) | 0.925 | 0.957 | 0.947 | 63 |

With the reranker the three embedders are equivalent on this set, so the default is the
fastest and smallest one, granite R2 (it is also slightly better without the reranker).

OCR (synthetic scans, Docling + EasyOCR, confidence threshold 0.2): character error rate 1-4%
on the contract and the manual; on the Constitution EasyOCR interleaves words of adjacent
justified lines and the CER is about 25%, although answers stay correct (correctness 0.94,
cited pages 1.0 on the `scans` dataset). With EasyOCR's default threshold (0.5) a third of
the text of noisy 150-dpi pages was lost.

RapidOCR with its Latin model (torch backend) keeps the word order on the same pages (median
page CER 0.07 against 0.20 for EasyOCR on six Constitution pages) but drops Italian accents
("liberta", "é" for "è"), and its models are not fetched by `fonti models pull`; Docling's
region order also varies on some pages, which the order-sensitive CER punishes. EasyOCR stays
the default; `parser.ocr_engine = "rapidocr"` is available for experiments.

The reranker gate was calibrated on the main dataset: every answerable question had a best
reranker score of at least 0.28, while 8 of the 12 unanswerable ones scored below 0.17; the
LLM has to reject the other four, which are topically close to the corpus.

## Adding questions

1. Find the passage in the parsed text (`uv run fonti eval check` prints quotes that are not
   found), copy a short verbatim quote and note its PDF page.
2. Add a line to `questions.jsonl` with a new id, the expected answer and tags; for
   unanswerable questions set `"answerable": false` and no evidence.
3. Run `uv run fonti eval check`, then an evaluation, and commit questions and report together.
