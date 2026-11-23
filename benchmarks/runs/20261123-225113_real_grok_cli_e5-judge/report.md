# Benchmark run 20261123-225113_real_grok_cli_e5-judge

- Corpus: `benchmarks\corpora\real` (fingerprint 212935fad86e7936, dataset c297130db4ea, 16 cases)
- LLM: grok_cli / cli-default / effort low
- Retrieval: top_k 4, chunks 800/150; prompts 452b67bf625f; git c057353 (uncommitted changes)
- Repeat 1, workers 2, judge True

## Headline

| Stage | Pass (95% CI) | Extra | Time | LLM calls | Cost |
| --- | --- | --- | --- | --- | --- |
| e2e | 14/16 (88%, CI 64-96%) | correct 12, correct_refusal 2, wrong_or_incomplete 1, partial 1; judge 4/4 (100%, CI 51-100%) | 257 s (p50 27.73 s) | 46 | $0.59 |

## e2e: by category

| Category | Pass |
| --- | --- |
| cross_lingual | 2/3 (67%, CI 21-94%) |
| doc_long | 1/1 (100%, CI 21-100%) |
| doc_lookup | 7/8 (88%, CI 53-98%) |
| doc_table | 2/2 (100%, CI 34-100%) |
| out_of_scope | 2/2 (100%, CI 34-100%) |

| Tag | Pass |
| --- | --- |
| bilingual_doc | 2/2 (100%, CI 34-100%) |
| chinese_question | 2/3 (67%, CI 21-94%) |
| flattened_table | 2/2 (100%, CI 34-100%) |

### e2e: failures

- **CN02** `{"outcome": "partial", "status": "partial", "route": "unstructured"}`
  - answer: - The Data Protection Officer can be contacted at Hang Seng Bank Limited, 83 Des Voeux Road Central, Hong Kong. (Unsupported statements were removed.)
- **HS07** `{"outcome": "wrong_or_incomplete", "missing": ["credit reference agencies"], "status": "grounded", "route": "unstructured"}`
  - answer: Hang Seng may share customer data with other third parties, as set out in section 8 of the notice [D1]. A truncated line also refers to sharing data — including by using application programming interfaces — with parties the customer has consented to share data with [D1]. The notice says this sharing may be local or outside Hong Kong [D1]. The full list of those parties, including the contents of s
