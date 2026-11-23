# Benchmark run 20261123-222800_v2_grok_cli_emb-multilingual-e5-larg

- Corpus: `benchmarks\corpora\v2` (fingerprint 6c810015f2343f34, dataset 7221ad189ca3, 40 cases)
- LLM: - / - / effort default
- Retrieval: top_k 4, chunks 800/150; prompts 452b67bf625f; git c057353 (uncommitted changes)
- Repeat 1, workers 3, judge False

## Headline

| Stage | Pass (95% CI) | Extra | Time | LLM calls | Cost |
| --- | --- | --- | --- | --- | --- |
| retrieval | 27/27 (100%, CI 88-100%) | hit@1 0.78, MRR 0.87, all gold sources 1.00 | 2 s (p50 0.04 s) | 0 | - |

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
