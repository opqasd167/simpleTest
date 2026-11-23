# Benchmark run 20261123-222850_v2_grok_cli_suggestions

- Corpus: `benchmarks\corpora\v2` (fingerprint d8350c506ac986ae, dataset 7221ad189ca3, 40 cases)
- LLM: grok_cli / cli-default / effort low
- Retrieval: top_k 4, chunks 800/150; prompts 452b67bf625f; git c057353 (uncommitted changes)
- Repeat 1, workers 2, judge False

## Headline

| Stage | Pass (95% CI) | Extra | Time | LLM calls | Cost |
| --- | --- | --- | --- | --- | --- |
| route | 37/37 (100%, CI 91-100%) |  | 118 s (p50 6.4 s) | 37 | $0.43 |
| sql | 16/18 (89%, CI 67-97%) | match 16, mismatch 2 | 86 s (p50 8.51 s) | 18 | $0.24 |
| e2e | 39/40 (98%, CI 87-100%) | correct 36, correct_refusal 3, false_refusal 1 | 543 s (p50 22.07 s) | 135 | $1.66 |

## route: by category

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
| sql_aggregate | 5/5 (100%, CI 57-100%) |
| sql_date | 1/1 (100%, CI 21-100%) |
| sql_join | 2/2 (100%, CI 34-100%) |
| sql_simple | 2/2 (100%, CI 34-100%) |

| Tag | Pass |
| --- | --- |
| ocr | 1/1 (100%, CI 21-100%) |
| prompt_injection | 2/2 (100%, CI 34-100%) |
| regional | 4/4 (100%, CI 51-100%) |
| status_filter | 1/1 (100%, CI 21-100%) |
| table | 1/1 (100%, CI 21-100%) |
| versioning | 3/3 (100%, CI 44-100%) |

## sql: by category

| Category | Pass |
| --- | --- |
| hybrid | 6/8 (75%, CI 41-93%) |
| sql_aggregate | 5/5 (100%, CI 57-100%) |
| sql_date | 1/1 (100%, CI 21-100%) |
| sql_join | 2/2 (100%, CI 34-100%) |
| sql_simple | 2/2 (100%, CI 34-100%) |

| Tag | Pass |
| --- | --- |
| regional | 1/2 (50%, CI 10-90%) |
| status_filter | 1/1 (100%, CI 21-100%) |
| versioning | 1/1 (100%, CI 21-100%) |

### sql: failures

- **H01** `{"outcome": "mismatch", "sql": "SELECT e.name, e.office, e.hire_date, e.carried_over_days, lr.leave_type, lr.start_date, lr.end_date, lr.working_days, lr.status\nFROM employees e\nJOIN leave_requests lr ON lr.employee_id = e.id\nWHERE e.name = 'Ben Ortiz'\n  AND lr.leave_type = 'annual'\n  AND lr.status = 'approved'\n  AND lr.start_date >= '2026-01-01'\n  AND lr.start_date < '2027-01-01'", "rows": [{"name": "Ben Ortiz", "office": "London", "hire_date": "2023-07-15", "carried_over_days": 0, "leave_type": "annual", "start_date": "2026-02-11", "end_date": "2026-02-16", "working_days": 4, "status"`
- **H02** `{"outcome": "mismatch", "sql": "SELECT e.name, e.office, e.hire_date, e.role, e.carried_over_days, lr.leave_type, lr.start_date, lr.end_date, lr.working_days, lr.status\nFROM employees e\nLEFT JOIN leave_requests lr\n  ON lr.employee_id = e.id\n AND lr.leave_type = 'annual'\n AND lr.status = 'approved'\nWHERE e.name = 'Priya Nair'\nORDER BY lr.start_date", "rows": [{"name": "Priya Nair", "office": "Singapore", "hire_date": "2024-02-01", "role": "Engineer", "carried_over_days": 0, "leave_type": "annual", "start_date": "2025-01-31", "end_date": "2025-02-06", "working_days": 5, "status": "approve`

## e2e: by category

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
| out_of_scope | 3/3 (100%, CI 44-100%) |
| sql_aggregate | 5/5 (100%, CI 57-100%) |
| sql_date | 1/1 (100%, CI 21-100%) |
| sql_join | 2/2 (100%, CI 34-100%) |
| sql_simple | 2/2 (100%, CI 34-100%) |

| Tag | Pass |
| --- | --- |
| ocr | 1/1 (100%, CI 21-100%) |
| prompt_injection | 1/2 (50%, CI 10-90%) |
| regional | 4/4 (100%, CI 51-100%) |
| status_filter | 1/1 (100%, CI 21-100%) |
| table | 1/1 (100%, CI 21-100%) |
| versioning | 3/3 (100%, CI 44-100%) |

### e2e: failures

- **A02** `{"outcome": "false_refusal", "status": "insufficient_evidence", "route": "unstructured"}`
  - answer: I could not find enough evidence in the documents or database to answer that.
