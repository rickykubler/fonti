# Valutazione: auto-rerank (scans)

- Data: 2026-10-04T16:08:48+00:00
- Domande: 40 (28 rispondibili)
- Parser: auto; chunk max 1500 caratteri; keyword: stemmed
- Embedding: BAAI/bge-m3
- Reranker: BAAI/bge-reranker-v2-m3
- LLM: qwen2.5:14b (ollama)
- Giudice: ollama:qwen2.5:14b
- Indice: 3 documenti, 71 pagine, 188 chunk

## Metriche

| Metrica | Valore |
|---|---|
| Recall@1 | 0.804 |
| Recall@3 | 0.804 |
| Recall@5 | 0.804 |
| Recall@10 | 0.804 |
| Recall nei candidati | 0.804 |
| MRR@10 | 0.821 |
| Rifiuti corretti (non rispondibili) | 0.917 |
| Falsi rifiuti (rispondibili) | 0.036 |
| Pagine citate corrette | 1 |
| Risposte che citano l'evidenza | 0.852 |
| Groundedness (giudice) | 0.789 |
| Correttezza (giudice) | 0.944 |
| Generazione p50 (s) | 2.655 |
| Generazione p95 (s) | 4.277 |
| Retrieval p50 (s) | 0.949 |
| Retrieval p95 (s) | 1.101 |

## Per tipo di domanda

| Tag | Domande | Recall@5 | MRR@10 |
|---|---|---|---|
| contratto | 7 | 1 | 1 |
| manuale | 7 | 1 | 1 |
| multi-passaggio | 1 | 0.5 | 1 |
| non-rispondibile | 12 | — | — |
| normativa | 14 | 0.607 | 0.643 |
| tabella-numerica | 1 | 1 | 1 |
| tabelle | 3 | 1 | 1 |

## Domande

| Id | Rank evidenze | Esito | Pagine ok | Grounded | Corretta |
|---|---|---|---|---|---|
| cost-01 | — | risposta | 1 | 0.5 | 1 |
| cost-02 | — | risposta | 1 | 1 | 0.5 |
| cost-03 | — | risposta | 1 | 0.25 | 1 |
| cost-04 | 1 | risposta | 1 | 1 | 1 |
| cost-05 | — | rifiuto errato | — | — | — |
| cost-06 | 1 | risposta | 1 | 0 | 1 |
| cost-07 | 1 | risposta | 1 | 0.167 | 0.5 |
| cost-08 | 1 | risposta | 1 | 1 | 1 |
| cost-09 | —, 1 | risposta | 1 | 1 | 1 |
| cost-10 | 1 | risposta | 1 | 1 | 1 |
| cost-11 | — | risposta | 1 | 1 | 1 |
| cost-12 | 1 | risposta | 1 | 1 | 1 |
| cost-13 | 1 | risposta | 1 | 1 | 1 |
| cost-14 | 1 | risposta | 1 | 0.667 | 0.5 |
| contratto-01 | 1 | risposta | 1 | 1 | 1 |
| contratto-02 | 1 | risposta | 1 | 1 | 1 |
| contratto-03 | 1 | risposta | 1 | 0 | 1 |
| contratto-04 | 1 | risposta | 1 | 1 | 1 |
| contratto-05 | 1 | risposta | 1 | 1 | 1 |
| contratto-06 | 1 | risposta | 1 | 1 | 1 |
| contratto-07 | 1 | risposta | 1 | 1 | 1 |
| manuale-01 | 1 | risposta | 1 | 0.5 | 1 |
| manuale-02 | 1 | risposta | 1 | 1 | 1 |
| manuale-03 | 1 | risposta | 1 | 1 | 1 |
| manuale-04 | 1 | risposta | 1 | 1 | 1 |
| manuale-05 | 1 | risposta | 1 | 1 | 1 |
| manuale-06 | 1 | risposta | 1 | 1 | 1 |
| manuale-07 | 1 | risposta | 1 | 1 | 1 |
| nr-01 | n/a | risposta non dovuta | — | 0 | — |
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
