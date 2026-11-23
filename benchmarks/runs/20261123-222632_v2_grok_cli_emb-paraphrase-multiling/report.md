# Benchmark run 20261123-222632_v2_grok_cli_emb-paraphrase-multiling

- Corpus: `benchmarks\corpora\v2` (fingerprint 954b6df6e8a62831, dataset 7221ad189ca3, 40 cases)
- LLM: - / - / effort default
- Retrieval: top_k 4, chunks 800/150; prompts 452b67bf625f; git c057353 (uncommitted changes)
- Repeat 1, workers 3, judge False

## Headline

| Stage | Pass (95% CI) | Extra | Time | LLM calls | Cost |
| --- | --- | --- | --- | --- | --- |
| retrieval | 26/27 (96%, CI 82-99%) | hit@1 0.63, MRR 0.76, all gold sources 0.96 | 0 s (p50 0.01 s) | 0 | - |

## retrieval: by category

| Category | Pass |
| --- | --- |
| adversarial | 1/2 (50%, CI 10-90%) |
| doc_long | 5/5 (100%, CI 57-100%) |
| doc_lookup | 5/5 (100%, CI 57-100%) |
| doc_regional | 2/2 (100%, CI 34-100%) |
| doc_scanned | 1/1 (100%, CI 21-100%) |
| doc_table | 2/2 (100%, CI 34-100%) |
| doc_versioning | 2/2 (100%, CI 34-100%) |
| hybrid | 8/8 (100%, CI 68-100%) |

| Tag | Pass |
| --- | --- |
| ocr | 1/1 (100%, CI 21-100%) |
| prompt_injection | 1/2 (50%, CI 10-90%) |
| regional | 4/4 (100%, CI 51-100%) |
| table | 1/1 (100%, CI 21-100%) |
| versioning | 3/3 (100%, CI 44-100%) |

### retrieval: failures

- **A01** `{"got": ["Leave_Policy_2026.pdf (page 2)", "Benefits_Guide_2026.pdf (page 2)", "Benefits_Guide_2026.pdf (page 3)", "Benefits_Guide_2026.pdf (page 2)"]}`
