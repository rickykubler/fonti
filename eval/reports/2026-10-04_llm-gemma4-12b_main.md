# Valutazione: llm-gemma4-12b (main)

- Data: 2026-10-04T19:58:34+00:00
- Domande: 59 (47 rispondibili)
- Parser: auto; chunk max 1500 caratteri; keyword: stemmed
- Embedding: BAAI/bge-m3
- Reranker: BAAI/bge-reranker-v2-m3
- LLM: gemma4:12b (ollama)
- Giudice: ollama:qwen2.5:14b
- Indice: 6 documenti, 130 pagine, 372 chunk

## Metriche

| Metrica | Valore |
|---|---|
| Recall@1 | 0.947 |
| Recall@3 | 0.957 |
| Recall@5 | 0.979 |
| Recall@10 | 1 |
| Recall nei candidati | 1 |
| MRR@10 | 0.966 |
| Rifiuti corretti (non rispondibili) | 1 |
| Falsi rifiuti (rispondibili) | 0.021 |
| Pagine citate corrette | 0.967 |
| Risposte che citano l'evidenza | 1 |
| Groundedness (giudice) | 0.91 |
| Correttezza (giudice) | 0.978 |
| Generazione p50 (s) | 3.528 |
| Generazione p95 (s) | 7.288 |
| Retrieval p50 (s) | 0.514 |
| Retrieval p95 (s) | 0.683 |

## Per tipo di domanda

| Tag | Domande | Recall@5 | MRR@10 |
|---|---|---|---|
| contratto | 7 | 1 | 1 |
| manuale | 13 | 1 | 1 |
| multi-passaggio | 2 | 1 | 1 |
| non-rispondibile | 12 | — | — |
| normativa | 14 | 1 | 1 |
| tabella-numerica | 5 | 0.8 | 0.683 |
| tabelle | 11 | 0.909 | 0.856 |
| verbale | 6 | 1 | 1 |

## Domande

| Id | Rank evidenze | Esito | Pagine ok | Grounded | Corretta |
|---|---|---|---|---|---|
| cost-01 | 1 | risposta | 1 | 1 | 1 |
| cost-02 | 1 | risposta | 1 | 1 | 1 |
| cost-03 | 1 | risposta | 0.75 | 0.8 | 1 |
| cost-04 | 1 | risposta | 1 | 1 | 1 |
| cost-05 | 1 | risposta | 1 | 1 | 1 |
| cost-06 | 1 | risposta | 1 | 1 | 1 |
| cost-07 | 1 | risposta | 1 | 1 | 1 |
| cost-08 | 1 | risposta | 1 | 1 | 1 |
| cost-09 | 2, 1 | risposta | 1 | 1 | 1 |
| cost-10 | 1 | risposta | 1 | 1 | 1 |
| cost-11 | 1 | risposta | 1 | 0.5 | 1 |
| cost-12 | 1 | risposta | 1 | 1 | 1 |
| cost-13 | 1 | risposta | 1 | 0.5 | 1 |
| cost-14 | 1 | risposta | 1 | 1 | 1 |
| istat-01 | 1 | risposta | 0.75 | 1 | 1 |
| istat-02 | 1 | risposta | 1 | 0.5 | 0.5 |
| istat-03 | 1 | risposta | 1 | 1 | 1 |
| istat-04 | 1 | risposta | 0.5 | 1 | 1 |
| istat-05 | 6 | rifiuto errato | — | — | — |
| istat-06 | 1 | risposta | 1 | 0 | 1 |
| istat-07 | 4 | risposta | 1 | 1 | 1 |
| agid-01 | 1 | risposta | 1 | 1 | 1 |
| agid-02 | 1 | risposta | 1 | 1 | 1 |
| agid-03 | 1, 1 | risposta | 1 | 0.667 | 1 |
| agid-04 | 1 | risposta | 1 | 1 | 1 |
| agid-05 | 1 | risposta | 1 | 1 | 1 |
| agid-06 | 1 | risposta | 0.5 | 0.889 | 1 |
| contratto-01 | 1 | risposta | 1 | 1 | 1 |
| contratto-02 | 1 | risposta | 1 | 0.5 | 1 |
| contratto-03 | 1 | risposta | 1 | 1 | 1 |
| contratto-04 | 1 | risposta | 1 | 1 | 1 |
| contratto-05 | 1 | risposta | 1 | 1 | 1 |
| contratto-06 | 1 | risposta | 1 | 1 | 1 |
| contratto-07 | 1 | risposta | 1 | 1 | 1 |
| verbale-01 | 1 | risposta | 1 | 1 | 1 |
| verbale-02 | 1 | risposta | 1 | 1 | 1 |
| verbale-03 | 1 | risposta | 1 | 1 | 1 |
| verbale-04 | 1 | risposta | 1 | 1 | 1 |
| verbale-05 | 1 | risposta | 1 | 1 | 1 |
| verbale-06 | 1 | risposta | 1 | 1 | 1 |
| manuale-01 | 1 | risposta | 1 | 0.5 | 1 |
| manuale-02 | 1 | risposta | 1 | 1 | 1 |
| manuale-03 | 1 | risposta | 1 | 1 | 1 |
| manuale-04 | 1 | risposta | 1 | 1 | 1 |
| manuale-05 | 1 | risposta | 1 | 1 | 1 |
| manuale-06 | 1 | risposta | 1 | 1 | 0.5 |
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
