# Valutazione: default (scans)

- Data: 2026-10-18T12:26:54+00:00
- Domande: 42 (28 rispondibili)
- Parser: auto; chunk max 1500 caratteri; keyword: stemmed
- Embedding: ibm-granite/granite-embedding-311m-multilingual-r2
- Reranker: BAAI/bge-reranker-v2-m3
- LLM: gemma4:12b (ollama)
- Giudice: ollama:qwen2.5:14b
- Indice: 3 documenti, 71 pagine, 188 chunk

## Metriche

| Metrica | Valore |
|---|---|
| Recall@1 | 0.857 |
| Recall@3 | 0.857 |
| Recall@5 | 0.857 |
| Recall@10 | 0.857 |
| Recall nei candidati | 0.857 |
| MRR@10 | 0.893 |
| Rifiuti corretti (non rispondibili) | 1 |
| Falsi rifiuti (rispondibili) | 0 |
| Pagine citate corrette | 0.97 |
| Risposte che citano l'evidenza | 0.964 |
| Groundedness (giudice) | 0.916 |
| Correttezza (giudice) | 0.982 |
| Generazione p50 (s) | 1 |
| Generazione p95 (s) | 2.358 |
| Retrieval p50 (s) | 0.185 |
| Retrieval p95 (s) | 0.205 |

## Per tipo di domanda

| Tag | Domande | Recall@5 | MRR@10 |
|---|---|---|---|
| contratto | 7 | 1 | 1 |
| manuale | 7 | 1 | 1 |
| multi-passaggio | 2 | 0.5 | 1 |
| non-rispondibile | 14 | — | — |
| normativa | 14 | 0.714 | 0.786 |
| tabella-numerica | 1 | 1 | 1 |
| tabelle | 3 | 1 | 1 |

## Domande

| Id | Rank evidenze | Esito | Pagine ok | Grounded | Corretta |
|---|---|---|---|---|---|
| cost-01 | — | risposta | 1 | 0.5 | 1 |
| cost-02 | — | risposta | 1 | 1 | 0.5 |
| cost-03 | —, 1 | risposta | 0.5 | 0.75 | 1 |
| cost-04 | 1 | risposta | 1 | 1 | 1 |
| cost-05 | 1 | risposta | 1 | 1 | 1 |
| cost-06 | 1 | risposta | 1 | 0 | 1 |
| cost-07 | 1 | risposta | 1 | 1 | 1 |
| cost-08 | 1 | risposta | 1 | 1 | 1 |
| cost-09 | —, 1 | risposta | 1 | 1 | 1 |
| cost-10 | 1 | risposta | 1 | 1 | 1 |
| cost-11 | — | risposta | 0.667 | 1 | 1 |
| cost-12 | 1 | risposta | 1 | 1 | 1 |
| cost-13 | 1 | risposta | 1 | 0.9 | 1 |
| cost-14 | 1 | risposta | 1 | 1 | 1 |
| contratto-01 | 1 | risposta | 1 | 1 | 1 |
| contratto-02 | 1 | risposta | 1 | 1 | 1 |
| contratto-03 | 1 | risposta | 1 | 1 | 1 |
| contratto-04 | 1 | risposta | 1 | 0.5 | 1 |
| contratto-05 | 1 | risposta | 1 | 1 | 1 |
| contratto-06 | 1 | risposta | 1 | 1 | 1 |
| contratto-07 | 1 | risposta | 1 | 1 | 1 |
| manuale-01 | 1 | risposta | 1 | 1 | 1 |
| manuale-02 | 1 | risposta | 1 | 1 | 1 |
| manuale-03 | 1 | risposta | 1 | 1 | 1 |
| manuale-04 | 1 | risposta | 1 | 1 | 1 |
| manuale-05 | 1 | risposta | 1 | 1 | 1 |
| manuale-06 | 1 | risposta | 1 | 1 | 1 |
| manuale-07 | 1 | risposta | 1 | 1 | 1 |
| nr-01 | n/a | rifiuto corretto | — | — | — |
| nr-02 | n/a | rifiuto corretto | — | — | — |
| nr-03 | n/a | rifiuto corretto | — | — | — |
| nr-04 | n/a | rifiuto corretto | — | — | — |
| nr-05 | n/a | rifiuto corretto | — | — | — |
| nr-06 | n/a | rifiuto corretto | — | — | — |
| nr-07 | n/a | rifiuto corretto | — | — | — |
| nr-08 | n/a | rifiuto corretto | — | — | — |
| nr-09 | n/a | rifiuto corretto | — | — | — |
| nr-10 | n/a | rifiuto corretto | — | — | — |
| nr-11 | n/a | rifiuto corretto | — | — | — |
| nr-12 | n/a | rifiuto corretto | — | — | — |
| nr-13 | n/a | rifiuto corretto | — | — | — |
| nr-14 | n/a | rifiuto corretto | — | — | — |
