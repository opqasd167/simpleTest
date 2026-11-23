# Benchmark run 20261123-222644_real_grok_cli_emb-paraphrase-multiling

- Corpus: `benchmarks\corpora\real` (fingerprint 16b720b15a5d4fe7, dataset c297130db4ea, 16 cases)
- LLM: - / - / effort default
- Retrieval: top_k 4, chunks 800/150; prompts 452b67bf625f; git c057353 (uncommitted changes)
- Repeat 1, workers 3, judge False

## Headline

| Stage | Pass (95% CI) | Extra | Time | LLM calls | Cost |
| --- | --- | --- | --- | --- | --- |
| retrieval | 14/14 (100%, CI 78-100%) | hit@1 0.93, MRR 0.96, all gold sources 1.00 | 0 s (p50 0.01 s) | 0 | - |

## retrieval: by category

| Category | Pass |
| --- | --- |
| cross_lingual | 3/3 (100%, CI 44-100%) |
| doc_long | 1/1 (100%, CI 21-100%) |
| doc_lookup | 8/8 (100%, CI 68-100%) |
| doc_table | 2/2 (100%, CI 34-100%) |

| Tag | Pass |
| --- | --- |
| bilingual_doc | 2/2 (100%, CI 34-100%) |
| chinese_question | 3/3 (100%, CI 44-100%) |
| flattened_table | 2/2 (100%, CI 34-100%) |
