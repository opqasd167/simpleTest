# Benchmark run 20261123-222550_v2_grok_cli_emb-default

- Corpus: `benchmarks\corpora\v2` (fingerprint d8350c506ac986ae, dataset 7221ad189ca3, 40 cases)
- LLM: - / - / effort default
- Retrieval: top_k 4, chunks 800/150; prompts 452b67bf625f; git c057353 (uncommitted changes)
- Repeat 1, workers 3, judge False

## Headline

| Stage | Pass (95% CI) | Extra | Time | LLM calls | Cost |
| --- | --- | --- | --- | --- | --- |
| retrieval | 27/27 (100%, CI 88-100%) | hit@1 0.74, MRR 0.84, all gold sources 1.00 | 4 s (p50 0.11 s) | 0 | - |

## retrieval: by category

| Category | Pass |
| --- | --- |
| adversarial | 2/2 (100%, CI 34-100%) |
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
| prompt_injection | 2/2 (100%, CI 34-100%) |
| regional | 4/4 (100%, CI 51-100%) |
| table | 1/1 (100%, CI 21-100%) |
| versioning | 3/3 (100%, CI 44-100%) |
