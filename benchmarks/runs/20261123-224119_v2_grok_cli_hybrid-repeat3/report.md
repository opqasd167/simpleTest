# Benchmark run 20261123-224119_v2_grok_cli_hybrid-repeat3

- Corpus: `benchmarks\corpora\v2` (fingerprint d8350c506ac986ae, dataset 7221ad189ca3, 8 cases)
- LLM: grok_cli / cli-default / effort low
- Retrieval: top_k 4, chunks 800/150; prompts 452b67bf625f; git c057353 (uncommitted changes)
- Repeat 3, workers 2, judge False

## Headline

| Stage | Pass (95% CI) | Extra | Time | LLM calls | Cost |
| --- | --- | --- | --- | --- | --- |
| e2e | 8/8 (100%, CI 68-100%) | correct 24 | 593 s (p50 46.2 s) | 96 | $1.22 |

## e2e: by category

| Category | Pass |
| --- | --- |
| hybrid | 8/8 (100%, CI 68-100%) |

| Tag | Pass |
| --- | --- |
| regional | 2/2 (100%, CI 34-100%) |
| versioning | 1/1 (100%, CI 21-100%) |
