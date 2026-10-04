# Valutazione: docling-rerank-retrieval (main)

- Data: 2026-10-04T16:03:54+00:00
- Domande: 59 (47 rispondibili)
- Parser: docling; chunk max 1500 caratteri; keyword: stemmed
- Embedding: BAAI/bge-m3
- Reranker: BAAI/bge-reranker-v2-m3
- LLM: qwen2.5:14b (ollama)
- Giudice: nessuno
- Indice: 6 documenti, 130 pagine, 412 chunk

## Metriche

| Metrica | Valore |
|---|---|
| Recall@1 | 0.925 |
| Recall@3 | 0.936 |
| Recall@5 | 0.957 |
| Recall@10 | 1 |
| Recall nei candidati | 1 |
| MRR@10 | 0.947 |
| Retrieval p50 (s) | 0.227 |
| Retrieval p95 (s) | 0.276 |

## Per tipo di domanda

| Tag | Domande | Recall@5 | MRR@10 |
|---|---|---|---|
| contratto | 7 | 1 | 1 |
| manuale | 13 | 1 | 1 |
| multi-passaggio | 2 | 1 | 1 |
| non-rispondibile | 12 | — | — |
| normativa | 14 | 1 | 1 |
| tabella-numerica | 5 | 0.6 | 0.501 |
| tabelle | 11 | 0.818 | 0.773 |
| verbale | 6 | 1 | 1 |

## Domande

| Id | Rank evidenze | Esito | Pagine ok | Grounded | Corretta |
|---|---|---|---|---|---|
| cost-01 | 1 | solo retrieval | — | — | — |
| cost-02 | 1 | solo retrieval | — | — | — |
| cost-03 | 1 | solo retrieval | — | — | — |
| cost-04 | 1 | solo retrieval | — | — | — |
| cost-05 | 1 | solo retrieval | — | — | — |
| cost-06 | 1 | solo retrieval | — | — | — |
| cost-07 | 1 | solo retrieval | — | — | — |
| cost-08 | 1 | solo retrieval | — | — | — |
| cost-09 | 2, 1 | solo retrieval | — | — | — |
| cost-10 | 1 | solo retrieval | — | — | — |
| cost-11 | 1 | solo retrieval | — | — | — |
| cost-12 | 1 | solo retrieval | — | — | — |
| cost-13 | 1 | solo retrieval | — | — | — |
| cost-14 | 1 | solo retrieval | — | — | — |
| istat-01 | 1 | solo retrieval | — | — | — |
| istat-02 | 1 | solo retrieval | — | — | — |
| istat-03 | 1 | solo retrieval | — | — | — |
| istat-04 | 1 | solo retrieval | — | — | — |
| istat-05 | 7 | solo retrieval | — | — | — |
| istat-06 | 4 | solo retrieval | — | — | — |
| istat-07 | 9 | solo retrieval | — | — | — |
| agid-01 | 1 | solo retrieval | — | — | — |
| agid-02 | 1 | solo retrieval | — | — | — |
| agid-03 | 1, 1 | solo retrieval | — | — | — |
| agid-04 | 1 | solo retrieval | — | — | — |
| agid-05 | 1 | solo retrieval | — | — | — |
| agid-06 | 1 | solo retrieval | — | — | — |
| contratto-01 | 1 | solo retrieval | — | — | — |
| contratto-02 | 1 | solo retrieval | — | — | — |
| contratto-03 | 1 | solo retrieval | — | — | — |
| contratto-04 | 1 | solo retrieval | — | — | — |
| contratto-05 | 1 | solo retrieval | — | — | — |
| contratto-06 | 1 | solo retrieval | — | — | — |
| contratto-07 | 1 | solo retrieval | — | — | — |
| verbale-01 | 1 | solo retrieval | — | — | — |
| verbale-02 | 1 | solo retrieval | — | — | — |
| verbale-03 | 1 | solo retrieval | — | — | — |
| verbale-04 | 1 | solo retrieval | — | — | — |
| verbale-05 | 1 | solo retrieval | — | — | — |
| verbale-06 | 1 | solo retrieval | — | — | — |
| manuale-01 | 1 | solo retrieval | — | — | — |
| manuale-02 | 1 | solo retrieval | — | — | — |
| manuale-03 | 1 | solo retrieval | — | — | — |
| manuale-04 | 1 | solo retrieval | — | — | — |
| manuale-05 | 1 | solo retrieval | — | — | — |
| manuale-06 | 1 | solo retrieval | — | — | — |
| manuale-07 | 1 | solo retrieval | — | — | — |
| nr-01 | n/a | solo retrieval | — | — | — |
| nr-02 | n/a | solo retrieval | — | — | — |
| nr-03 | n/a | solo retrieval | — | — | — |
| nr-04 | n/a | solo retrieval | — | — | — |
| nr-05 | n/a | solo retrieval | — | — | — |
| nr-06 | n/a | solo retrieval | — | — | — |
| nr-07 | n/a | solo retrieval | — | — | — |
| nr-08 | n/a | solo retrieval | — | — | — |
| nr-09 | n/a | solo retrieval | — | — | — |
| nr-10 | n/a | solo retrieval | — | — | — |
| nr-11 | n/a | solo retrieval | — | — | — |
| nr-12 | n/a | solo retrieval | — | — | — |
