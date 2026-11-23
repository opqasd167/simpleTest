# Benchmark run 20261123-215903_v2_grok_cli_baseline

- Corpus: `benchmarks\corpora\v2` (fingerprint 46c6483b2529c197, dataset 9b8b6ebab962, 40 cases)
- LLM: grok_cli / cli-default / effort low
- Retrieval: top_k 4, chunks 800/150; prompts 9aa37130be8c; git c057353 (uncommitted changes)
- Repeat 1, workers 2, judge False

## Headline

| Stage | Pass (95% CI) | Extra | Time | LLM calls | Cost |
| --- | --- | --- | --- | --- | --- |
| route | 34/36 (94%, CI 82-98%) |  | 126 s (p50 6.63 s) | 36 | $0.45 |
| sql | 13/18 (72%, CI 49-88%) | match 13, mismatch 5 | 123 s (p50 12.84 s) | 18 | $0.25 |
| e2e | 37/40 (92%, CI 80-97%) | correct 33, correct_refusal 4, false_refusal 3 | 543 s (p50 26.45 s) | 132 | $1.53 |

## route: by category

| Category | Pass |
| --- | --- |
| adversarial | 2/2 (100%, CI 34-100%) |
| doc_long | 5/5 (100%, CI 57-100%) |
| doc_lookup | 5/5 (100%, CI 57-100%) |
| doc_regional | 2/2 (100%, CI 34-100%) |
| doc_table | 2/2 (100%, CI 34-100%) |
| doc_versioning | 2/2 (100%, CI 34-100%) |
| hybrid | 6/8 (75%, CI 41-93%) |
| sql_aggregate | 5/5 (100%, CI 57-100%) |
| sql_date | 1/1 (100%, CI 21-100%) |
| sql_join | 2/2 (100%, CI 34-100%) |
| sql_simple | 2/2 (100%, CI 34-100%) |

| Tag | Pass |
| --- | --- |
| prompt_injection | 2/2 (100%, CI 34-100%) |
| regional | 4/4 (100%, CI 51-100%) |
| status_filter | 1/1 (100%, CI 21-100%) |
| table | 1/1 (100%, CI 21-100%) |
| versioning | 3/3 (100%, CI 44-100%) |

### route: failures

- **H05** `{"got": "structured"}`
- **H07** `{"got": "structured"}`

## sql: by category

| Category | Pass |
| --- | --- |
| hybrid | 3/8 (38%, CI 14-69%) |
| sql_aggregate | 5/5 (100%, CI 57-100%) |
| sql_date | 1/1 (100%, CI 21-100%) |
| sql_join | 2/2 (100%, CI 34-100%) |
| sql_simple | 2/2 (100%, CI 34-100%) |

| Tag | Pass |
| --- | --- |
| regional | 0/2 (0%, CI 0-66%) |
| status_filter | 1/1 (100%, CI 21-100%) |
| versioning | 0/1 (0%, CI 0-79%) |

### sql: failures

- **H01** `{"outcome": "mismatch", "sql": "SELECT e.name, e.hire_date, e.carried_over_days, lr.start_date, lr.end_date, lr.working_days\nFROM employees e\nLEFT JOIN leave_requests lr\n  ON lr.employee_id = e.id\n AND lr.leave_type = 'annual'\n AND lr.status = 'approved'\n AND lr.start_date < '2027-01-01'\n AND lr.end_date >= '2026-01-01'\nWHERE e.name = 'Ben Ortiz'", "rows": [{"name": "Ben Ortiz", "hire_date": "2023-07-15", "carried_over_days": 0, "start_date": "2026-02-11", "end_date": "2026-02-16", "working_days": 4}, {"name": "Ben Ortiz", "hire_date": "2023-07-15", "carried_over_days": 0, "start_date"`
- **H02** `{"outcome": "mismatch", "sql": "SELECT e.name, e.hire_date, e.carried_over_days, COALESCE(SUM(lr.working_days), 0) AS approved_annual_working_days FROM employees e LEFT JOIN leave_requests lr ON lr.employee_id = e.id AND lr.leave_type = 'annual' AND lr.status = 'approved' AND lr.start_date <= '2026-12-31' AND lr.end_date >= '2026-01-01' WHERE e.name = 'Priya Nair' GROUP BY e.id, e.name, e.hire_date, e.carried_over_days", "rows": [{"name": "Priya Nair", "hire_date": "2024-02-01", "carried_over_days": 0, "approved_annual_working_days": 19}], "gold_rows": [["Singapore", "2024-02-01", 0, 19]]}`
- **H04** `{"outcome": "mismatch", "sql": "SELECT e.name AS employee_name, e.role, e.office, d.name AS department_name, x.category, x.amount_usd, x.expense_date, x.status, approver.name AS approved_by_name\nFROM expenses AS x\nJOIN employees AS e ON e.id = x.employee_id\nLEFT JOIN departments AS d ON d.id = e.department_id\nLEFT JOIN employees AS approver ON approver.id = x.approved_by\nWHERE e.name = 'Ana Lee'\n  AND x.category = 'travel'\n  AND x.expense_date >= '2025-06-01'\n  AND x.expense_date < '2025-07-01'", "rows": [{"employee_name": "Ana Lee", "role": "Engineer", "office": "London", "department_`
- **H06** `{"outcome": "mismatch", "sql": "SELECT employees.name, expenses.category, expenses.status, expenses.expense_date, expenses.amount_usd FROM expenses JOIN employees ON employees.id = expenses.employee_id WHERE employees.name = 'Marcus Tan' AND expenses.category = 'meals' AND expenses.expense_date >= '2026-03-01' AND expenses.expense_date < '2026-04-01' ORDER BY expenses.expense_date, expenses.id", "rows": [{"name": "Marcus Tan", "category": "meals", "status": "approved", "expense_date": "2026-03-04", "amount_usd": 70.0}], "gold_rows": [["Singapore", 70.0]]}`
- **H08** `{"outcome": "mismatch", "sql": "SELECT e.name AS employee_name, e.office, x.expense_date, x.category, x.amount_usd, x.status\nFROM expenses x\nJOIN employees e ON e.id = x.employee_id\nWHERE e.office = 'London'\n  AND x.category = 'meals'\n  AND x.status = 'approved'\n  AND x.expense_date >= '2026-01-01'\n  AND x.expense_date < '2027-01-01'\nORDER BY e.name, x.expense_date, x.id", "rows": [{"employee_name": "Ben Ortiz", "office": "London", "expense_date": "2026-03-09", "category": "meals", "amount_usd": 18.09, "status": "approved"}, {"employee_name": "Ben Ortiz", "office": "London", "expense_d`

## e2e: by category

| Category | Pass |
| --- | --- |
| adversarial | 2/2 (100%, CI 34-100%) |
| doc_long | 5/5 (100%, CI 57-100%) |
| doc_lookup | 5/5 (100%, CI 57-100%) |
| doc_regional | 2/2 (100%, CI 34-100%) |
| doc_table | 2/2 (100%, CI 34-100%) |
| doc_versioning | 2/2 (100%, CI 34-100%) |
| hybrid | 5/8 (62%, CI 31-86%) |
| known_gap | 1/1 (100%, CI 21-100%) |
| out_of_scope | 3/3 (100%, CI 44-100%) |
| sql_aggregate | 5/5 (100%, CI 57-100%) |
| sql_date | 1/1 (100%, CI 21-100%) |
| sql_join | 2/2 (100%, CI 34-100%) |
| sql_simple | 2/2 (100%, CI 34-100%) |

| Tag | Pass |
| --- | --- |
| ocr | 1/1 (100%, CI 21-100%) |
| prompt_injection | 2/2 (100%, CI 34-100%) |
| regional | 2/4 (50%, CI 15-85%) |
| status_filter | 1/1 (100%, CI 21-100%) |
| table | 1/1 (100%, CI 21-100%) |
| versioning | 2/3 (67%, CI 21-94%) |

### e2e: failures

- **H02** `{"outcome": "false_refusal", "missing": ["19", "18"], "status": "insufficient_evidence", "route": "hybrid", "sql": "SELECT e.name, e.office, e.role, e.hire_date, e.carried_over_days, COALESCE(SUM(lr.working_days), 0) AS approved_annual_leave_working_days_2026\nFROM employees e\nLEFT JOIN leave_requests lr\n  ON lr.employee_id = e.id\n AND lr.leave_type = 'annual'\n AND lr.status = 'approved'\n AND lr.start_date >= '2026-01-01'\n AND lr.start_date <= '2026-12-31'\nWHERE e.name = 'Priya Nair'\nGROUP BY e.id, e.name, e.office, e.role, e.hire_date, e.carried_over_days"}`
  - answer: I could not find enough evidence in the documents or database to answer that.
- **H04** `{"outcome": "false_refusal", "missing": ["1200", "1000"], "status": "insufficient_evidence", "route": "hybrid", "sql": "SELECT employees.name, employees.role, employees.office, expenses.category, expenses.amount_usd, expenses.expense_date, expenses.status FROM expenses JOIN employees ON employees.id = expenses.employee_id WHERE employees.name = 'Ana Lee' AND expenses.category = 'travel' AND expenses.expense_date >= '2025-06-01' AND expenses.expense_date < '2025-07-01'"}`
  - answer: I could not find enough evidence in the documents or database to answer that.
- **H06** `{"outcome": "false_refusal", "missing": ["70", "60"], "status": "insufficient_evidence", "route": "hybrid", "sql": "SELECT e.name, x.status, SUM(x.amount_usd) AS meal_amount_usd FROM employees e JOIN expenses x ON x.employee_id = e.id WHERE e.name = 'Marcus Tan' AND x.category = 'meals' AND x.expense_date >= '2026-03-01' AND x.expense_date < '2026-04-01' GROUP BY e.name, x.status"}`
  - answer: I could not find enough evidence in the documents or database to answer that.
