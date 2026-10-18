# Valutazione: default (main)

- Data: 2026-10-18T12:23:37+00:00
- Domande: 75 (61 rispondibili)
- Parser: auto; chunk max 1500 caratteri; keyword: stemmed
- Embedding: ibm-granite/granite-embedding-311m-multilingual-r2
- Reranker: BAAI/bge-reranker-v2-m3
- LLM: gemma4:12b (ollama)
- Giudice: ollama:qwen2.5:14b
- Indice: 8 documenti, 362 pagine, 1373 chunk

## Metriche

| Metrica | Valore |
|---|---|
| Recall@1 | 0.795 |
| Recall@3 | 0.902 |
| Recall@5 | 0.934 |
| Recall@10 | 0.984 |
| Recall nei candidati | 0.984 |
| MRR@10 | 0.865 |
| Rifiuti corretti (non rispondibili) | 1 |
| Falsi rifiuti (rispondibili) | 0.033 |
| Pagine citate corrette | 0.893 |
| Risposte che citano l'evidenza | 0.966 |
| Groundedness (giudice) | 0.902 |
| Correttezza (giudice) | 0.975 |
| Generazione p50 (s) | 1.57 |
| Generazione p95 (s) | 4.314 |
| Retrieval p50 (s) | 0.202 |
| Retrieval p95 (s) | 0.236 |

## Per tipo di domanda

| Tag | Domande | Recall@5 | MRR@10 |
|---|---|---|---|
| contratto | 7 | 1 | 1 |
| manuale | 13 | 1 | 1 |
| multi-passaggio | 3 | 1 | 1 |
| non-rispondibile | 14 | — | — |
| normativa | 28 | 0.929 | 0.793 |
| tabella-numerica | 5 | 0.6 | 0.517 |
| tabelle | 11 | 0.818 | 0.78 |
| verbale | 6 | 1 | 1 |

## Domande

| Id | Rank evidenze | Esito | Pagine ok | Grounded | Corretta |
|---|---|---|---|---|---|
| cost-01 | 1 | risposta | 1 | 1 | 1 |
| cost-02 | 1 | risposta | 1 | 1 | 1 |
| cost-03 | 1, 1 | risposta | 1 | 1 | 1 |
| cost-04 | 1 | risposta | 1 | 1 | 1 |
| cost-05 | 1 | risposta | 1 | 1 | 1 |
| cost-06 | 1 | risposta | 1 | 1 | 1 |
| cost-07 | 1 | risposta | 1 | 1 | 1 |
| cost-08 | 1 | risposta | 1 | 1 | 1 |
| cost-09 | 2, 1 | risposta | 1 | 1 | 1 |
| cost-10 | 1 | risposta | 1 | 1 | 1 |
| cost-11 | 1 | risposta | 1 | 1 | 1 |
| cost-12 | 1 | risposta | 1 | 1 | 1 |
| cost-13 | 1 | risposta | 1 | 1 | 1 |
| cost-14 | 1 | risposta | 1 | 1 | 1 |
| istat-01 | 1 | risposta | 0.667 | 1 | 1 |
| istat-02 | 1 | risposta | 1 | 0.5 | 0.5 |
| istat-03 | 1 | risposta | 1 | 1 | 1 |
| istat-04 | 1 | risposta | 1 | 1 | 1 |
| istat-05 | 6 | rifiuto errato | — | — | — |
| istat-06 | 6 | risposta | 1 | 0 | 1 |
| istat-07 | 4 | risposta | 1 | 1 | 1 |
| agid-01 | 1 | risposta | 1 | 1 | 1 |
| agid-02 | 1 | risposta | 1 | 1 | 1 |
| agid-03 | 1, 1 | risposta | 1 | 1 | 1 |
| agid-04 | 1 | risposta | 0.875 | 0.679 | 0.5 |
| agid-05 | 1 | risposta | 1 | 1 | 1 |
| agid-06 | 1 | risposta | 0.5 | 0.889 | 1 |
| contratto-01 | 1 | risposta | 1 | 1 | 1 |
| contratto-02 | 1 | risposta | 1 | 1 | 1 |
| contratto-03 | 1 | risposta | 1 | 1 | 1 |
| contratto-04 | 1 | risposta | 1 | 1 | 1 |
| contratto-05 | 1 | risposta | 1 | 1 | 1 |
| contratto-06 | 1 | risposta | 0.5 | 1 | 1 |
| contratto-07 | 1 | risposta | 1 | 1 | 1 |
| verbale-01 | 1 | risposta | 1 | 1 | 1 |
| verbale-02 | 1 | risposta | 1 | 1 | 1 |
| verbale-03 | 1 | risposta | 1 | 1 | 1 |
| verbale-04 | 1 | risposta | 1 | 1 | 1 |
| verbale-05 | 1 | risposta | 1 | 1 | 1 |
| verbale-06 | 1 | risposta | 1 | 0.5 | 1 |
| manuale-01 | 1 | risposta | 1 | 1 | 1 |
| manuale-02 | 1 | risposta | 1 | 1 | 1 |
| manuale-03 | 1 | risposta | 1 | 1 | 1 |
| manuale-04 | 1 | risposta | 1 | 1 | 1 |
| manuale-05 | 1 | risposta | 1 | 1 | 1 |
| manuale-06 | 1 | risposta | 1 | 1 | 0.5 |
| manuale-07 | 1 | risposta | 1 | 1 | 1 |
| gdpr-01 | 1 | risposta | 1 | 1 | 1 |
| gdpr-02 | 1 | risposta | 1 | 1 | 1 |
| gdpr-03 | 2 | risposta | 0.5 | 1 | 1 |
| gdpr-04 | 1 | risposta | 0.5 | 0 | 1 |
| gdpr-05 | 1 | risposta | 0.5 | 1 | 1 |
| gdpr-06 | 1 | risposta | 1 | 0 | 1 |
| gdpr-07 | 4 | risposta | 1 | 0.5 | 1 |
| aiact-01 | 2 | risposta | 0.167 | 0.875 | 1 |
| aiact-02 | 3 | risposta | 1 | 1 | 1 |
| aiact-03 | 2 | risposta | 0.5 | 0.7 | 1 |
| aiact-04 | 8 | rifiuto errato | — | — | — |
| aiact-05 | 2 | risposta | 0.5 | 0.8 | 1 |
| aiact-06 | 2 | risposta | 0.5 | 0.75 | 1 |
| aiact-07 | — | risposta | 0 | 1 | 1 |
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
