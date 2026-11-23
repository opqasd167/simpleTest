# Benchmark run 20261123-222556_real_grok_cli_emb-default

- Corpus: `benchmarks\corpora\real` (fingerprint 73fb0a0229a47807, dataset c297130db4ea, 16 cases)
- LLM: - / - / effort default
- Retrieval: top_k 4, chunks 800/150; prompts 452b67bf625f; git c057353 (uncommitted changes)
- Repeat 1, workers 3, judge False

## Headline

| Stage | Pass (95% CI) | Extra | Time | LLM calls | Cost |
| --- | --- | --- | --- | --- | --- |
| retrieval | 13/14 (93%, CI 68-99%) | hit@1 0.71, MRR 0.80, all gold sources 0.93 | 2 s (p50 0.11 s) | 0 | - |

## retrieval: by category

| Category | Pass |
| --- | --- |
| cross_lingual | 2/3 (67%, CI 21-94%) |
| doc_long | 1/1 (100%, CI 21-100%) |
| doc_lookup | 8/8 (100%, CI 68-100%) |
| doc_table | 2/2 (100%, CI 34-100%) |

| Tag | Pass |
| --- | --- |
| bilingual_doc | 2/2 (100%, CI 34-100%) |
| chinese_question | 2/3 (67%, CI 21-94%) |
| flattened_table | 2/2 (100%, CI 34-100%) |

### retrieval: failures

- **CN01** `{"got": ["maintenance_schedule_tchi.pdf (page 1)", "maintenance_schedule_tchi.pdf (page 2)", "maintenance_schedule_tchi.pdf (page 1)", "hang_seng_bank_card_notice_e.pdf (page 2)"]}`
