-- Demo data that matches the test documents in data/raw/docs (Brightwave Analytics, fictional)
DROP TABLE IF EXISTS expenses;
DROP TABLE IF EXISTS employees;
CREATE TABLE employees(
  id INTEGER PRIMARY KEY, name TEXT, department TEXT, role TEXT,
  hire_date TEXT,
  leave_days_used INTEGER,    -- annual leave days taken in the 2026 leave year
  carried_over_days INTEGER); -- unused days carried over from 2025 into 2026
CREATE TABLE expenses(
  id INTEGER PRIMARY KEY, employee_id INTEGER REFERENCES employees(id),
  category TEXT, amount_usd REAL, expense_date TEXT);
INSERT INTO employees VALUES
  (1,'Ana Lee','Engineering','Engineer','2022-03-01',12,3),
  (2,'Ben Ortiz','Engineering','Engineer','2023-07-15',22,0),
  (3,'Chen Wu','Finance','Analyst','2021-01-10',5,0),
  (4,'Dana Kim','Sales','Manager','2020-05-20',18,5);
INSERT INTO expenses VALUES
  (1,1,'travel',420.00,'2026-09-03'),
  (2,2,'meals',95.50,'2026-09-12'),
  (3,4,'travel',1830.00,'2026-10-01'),
  (4,3,'software',60.00,'2026-10-05');
