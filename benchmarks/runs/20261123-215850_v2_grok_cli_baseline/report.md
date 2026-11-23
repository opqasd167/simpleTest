# Benchmark run 20261123-215850_v2_grok_cli_baseline

- Corpus: `benchmarks\corpora\v2` (fingerprint 46c6483b2529c197, dataset 9b8b6ebab962, 40 cases)
- LLM: - / - / effort default
- Retrieval: top_k 4, chunks 800/150; prompts 9aa37130be8c; git c057353 (uncommitted changes)
- Repeat 1, workers 3, judge False

## Headline

| Stage | Pass (95% CI) | Extra | Time | LLM calls | Cost |
| --- | --- | --- | --- | --- | --- |
| retrieval | 25/26 (96%, CI 81-99%) | hit@1 0.73, MRR 0.83, all gold sources 0.96 | 3 s (p50 0.11 s) | 0 | - |

## retrieval: by category

| Category | Pass |
| --- | --- |
| adversarial | 2/2 (100%, CI 34-100%) |
| doc_long | 5/5 (100%, CI 57-100%) |
| doc_lookup | 5/5 (100%, CI 57-100%) |
| doc_regional | 2/2 (100%, CI 34-100%) |
| doc_table | 2/2 (100%, CI 34-100%) |
| doc_versioning | 2/2 (100%, CI 34-100%) |
| hybrid | 7/8 (88%, CI 53-98%) |

| Tag | Pass |
| --- | --- |
| prompt_injection | 2/2 (100%, CI 34-100%) |
| regional | 3/4 (75%, CI 30-95%) |
| table | 1/1 (100%, CI 21-100%) |
| versioning | 3/3 (100%, CI 44-100%) |

### retrieval: failures

- **H02** `{"got": ["Leave_Policy_2026.pdf (page 1)", "Benefits_Guide_2026.pdf (page 2)", "Leave_Policy_2026.pdf (page 2)", "Leave_Policy_2026.pdf (page 1)"]}`
