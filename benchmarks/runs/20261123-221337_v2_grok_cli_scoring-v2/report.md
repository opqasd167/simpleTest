# Benchmark run 20261123-221337_v2_grok_cli_scoring-v2

- Corpus: `benchmarks\corpora\v2` (fingerprint 2e867bb5dd77e08d, dataset 47a0d6de1852, 8 cases)
- LLM: grok_cli / cli-default / effort low
- Retrieval: top_k 4, chunks 800/150; prompts 9aa37130be8c; git c057353 (uncommitted changes)
- Repeat 1, workers 2, judge False

## Headline

| Stage | Pass (95% CI) | Extra | Time | LLM calls | Cost |
| --- | --- | --- | --- | --- | --- |
| route | 8/8 (100%, CI 68-100%) |  | 26 s (p50 6.64 s) | 8 | $0.08 |
| sql | 4/8 (50%, CI 22-78%) | mismatch 4, match 4 | 71 s (p50 13.45 s) | 8 | $0.12 |

## route: by category

| Category | Pass |
| --- | --- |
| hybrid | 8/8 (100%, CI 68-100%) |

| Tag | Pass |
| --- | --- |
| regional | 2/2 (100%, CI 34-100%) |
| versioning | 1/1 (100%, CI 21-100%) |

## sql: by category

| Category | Pass |
| --- | --- |
| hybrid | 4/8 (50%, CI 22-78%) |

| Tag | Pass |
| --- | --- |
| regional | 0/2 (0%, CI 0-66%) |
| versioning | 0/1 (0%, CI 0-79%) |

### sql: failures

- **H01** `{"outcome": "mismatch", "sql": "SELECT e.name, e.carried_over_days, COALESCE(SUM(lr.working_days), 0) AS approved_annual_working_days FROM employees e LEFT JOIN leave_requests lr ON lr.employee_id = e.id AND lr.leave_type = 'annual' AND lr.status = 'approved' AND lr.start_date >= '2026-01-01' AND lr.start_date < '2027-01-01' WHERE e.name = 'Ben Ortiz' GROUP BY e.id, e.name, e.carried_over_days", "rows": [{"name": "Ben Ortiz", "carried_over_days": 0, "approved_annual_working_days": 22}], "gold_rows": [["2023-07-15", 0, 22]]}`
- **H02** `{"outcome": "mismatch", "sql": "SELECT e.name, e.carried_over_days, COALESCE(SUM(lr.working_days), 0) AS approved_annual_working_days_2026 FROM employees e LEFT JOIN leave_requests lr ON lr.employee_id = e.id AND lr.leave_type = 'annual' AND lr.status = 'approved' AND lr.start_date >= '2026-01-01' AND lr.start_date < '2027-01-01' WHERE e.name = 'Priya Nair' GROUP BY e.id, e.name, e.carried_over_days", "rows": [{"name": "Priya Nair", "carried_over_days": 0, "approved_annual_working_days_2026": 19}], "gold_rows": [["Singapore", "2024-02-01", 0, 19]]}`
- **H04** `{"outcome": "mismatch", "sql": "SELECT emp.name AS employee_name, emp.office, emp.role, dept.name AS department_name, exp.category, exp.amount_usd, exp.expense_date, exp.status, approver.name AS approved_by_name\nFROM expenses AS exp\nJOIN employees AS emp ON emp.id = exp.employee_id\nLEFT JOIN departments AS dept ON dept.id = emp.department_id\nLEFT JOIN employees AS approver ON approver.id = exp.approved_by\nWHERE emp.name = 'Ana Lee'\n  AND exp.category = 'travel'\n  AND exp.expense_date >= '2025-06-01'\n  AND exp.expense_date < '2025-07-01'", "rows": [{"employee_name": "Ana Lee", "office":`
- **H06** `{"outcome": "mismatch", "sql": "SELECT e.name, x.expense_date, x.category, x.amount_usd, x.status\nFROM employees e\nJOIN expenses x ON x.employee_id = e.id\nWHERE e.name = 'Marcus Tan'\n  AND x.category = 'meals'\n  AND x.expense_date >= '2026-03-01'\n  AND x.expense_date < '2026-04-01'", "rows": [{"name": "Marcus Tan", "expense_date": "2026-03-04", "category": "meals", "amount_usd": 70.0, "status": "approved"}], "gold_rows": [["Singapore", 70.0]]}`
