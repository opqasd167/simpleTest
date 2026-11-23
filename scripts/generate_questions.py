"""Generate a large synthetic question set (default 10,000) with ground truth.

Real projects take questions from user logs; this script simulates that so the scale-eval
flow can be demonstrated. Each row belongs to an intent (one fact the question asks about).
Rows are drawn with a skewed popularity, like real traffic: a few questions are asked a lot.

For SQL facts the expected answer is COMPUTED by running truth_sql against the database,
never typed by hand.

Usage:  python scripts/generate_questions.py --n 10000 --out tests/eval/questions_10k.jsonl
"""
import argparse
import json
import random
import sqlite3
from pathlib import Path

# id, group, route, status, source (for retrieval checks), expect (or truth_sql), paraphrases
FACTS = [
    # ---- documents: Leave_Policy.pdf ----
    ("leave_under3", "docs", "unstructured", "grounded", "Leave_Policy.pdf", ["20"], [
        "How many days of annual leave do employees with less than 3 years of service get?",
        "What is the annual leave entitlement for new staff?",
        "If I joined two years ago, how many holiday days do I get per year?"]),
    ("leave_over3", "docs", "unstructured", "grounded", "Leave_Policy.pdf", ["25"], [
        "How many annual leave days do employees with 3 or more years of service get?",
        "What is the leave entitlement after three years at the company?"]),
    ("carry_max", "docs", "unstructured", "grounded", "Leave_Policy.pdf", ["5"], [
        "How many unused leave days can I carry over to next year?",
        "What is the maximum carry-over of annual leave?"]),
    ("carry_deadline", "docs", "unstructured", "grounded", "Leave_Policy.pdf", ["31 March"], [
        "By when must carried-over leave be used?",
        "What is the deadline for taking carried-over holiday?"]),
    ("sick_days", "docs", "unstructured", "grounded", "Leave_Policy.pdf", ["10"], [
        "How many days of paid sick leave do we get?",
        "What is the paid sick leave allowance per year?"]),
    ("medical_cert", "docs", "unstructured", "grounded", "Leave_Policy.pdf", ["3"], [
        "When do I need a medical certificate for sick leave?",
        "After how many days of sickness is a doctor's note required?"]),
    ("parental_primary", "docs", "unstructured", "grounded", "Leave_Policy.pdf", ["16"], [
        "How much paid parental leave does the primary caregiver get?",
        "How many weeks of parental leave for the primary carer?"]),
    ("leave_notice", "docs", "unstructured", "grounded", "Leave_Policy.pdf", ["10"], [
        "How far in advance must I request a holiday of 5 or more days?",
        "What notice is required for a long leave request?"]),
    ("bereavement", "docs", "unstructured", "grounded", "Leave_Policy.pdf", ["5"], [
        "How many days of bereavement leave are allowed?",
        "What is the compassionate leave allowance for close family?"]),
    ("over_entitlement", "docs", "unstructured", "grounded", "Leave_Policy.pdf", ["HR Director"], [
        "Who must approve leave beyond my entitlement?",
        "What happens if I take more annual leave than I am entitled to?"]),
    # ---- documents: IT_Security_Policy.pdf ----
    ("pw_length", "docs", "unstructured", "grounded", "IT_Security_Policy.pdf", ["14"], [
        "How long must a password be?",
        "What is the minimum password length?"]),
    ("pw_rotation", "docs", "unstructured", "grounded", "IT_Security_Policy.pdf", ["90"], [
        "How often must passwords be changed?",
        "What is the password rotation period?"]),
    ("lockout", "docs", "unstructured", "grounded", "IT_Security_Policy.pdf", ["15"], [
        "How long is an account locked after too many failed sign-ins?",
        "What happens after 5 failed login attempts?"]),
    ("incident", "docs", "unstructured", "grounded", "IT_Security_Policy.pdf", ["1 hour"], [
        "How quickly must I report a security incident?",
        "What is the deadline for reporting a phishing email?"]),
    ("classification", "docs", "unstructured", "grounded", "IT_Security_Policy.pdf",
     ["Public", "Internal", "Confidential", "Restricted"], [
        "What are the data classification levels?",
        "List the four levels of data classification."]),
    # ---- documents: Travel_and_Expense_Policy.docx ----
    ("meal_limit", "docs", "unstructured", "grounded", "Travel_and_Expense_Policy.docx", ["75"], [
        "What is the daily meal expense limit?",
        "How much can I spend on meals per day?"]),
    ("hotel_limit", "docs", "unstructured", "grounded", "Travel_and_Expense_Policy.docx", ["250"], [
        "What is the hotel limit per night?",
        "How much can I spend on a hotel room per night?"]),
    ("vp_rule", "docs", "unstructured", "grounded", "Travel_and_Expense_Policy.docx", ["VP"], [
        "Who must approve a trip that costs more than $1,500?",
        "Does an expensive trip need special approval?"]),
    ("claim_window", "docs", "unstructured", "grounded", "Travel_and_Expense_Policy.docx", ["30"], [
        "Within how many days must I submit an expense claim?",
        "What is the deadline for expense claims?"]),
    # ---- documents: Employee_Handbook.docx ----
    ("office_days", "docs", "unstructured", "grounded", "Employee_Handbook.docx", ["3"], [
        "How many days per week do employees have to work in the office?",
        "What is the hybrid working rule?"]),
    ("learning_budget", "docs", "unstructured", "grounded", "Employee_Handbook.docx", ["1000"], [
        "What is the annual learning budget?",
        "How much can I spend on training courses per year?"]),
    ("probation", "docs", "unstructured", "grounded", "Employee_Handbook.docx", ["6"], [
        "How long is the probation period?",
        "How many months of probation do new hires have?"]),
    # ---- SQL: expected answers computed from truth_sql ----
    ("hc_eng", "sql", "structured", "grounded", None,
     "SELECT COUNT(*) FROM employees WHERE department='Engineering'", [
        "How many people work in Engineering?",
        "What is the headcount of the Engineering department?"]),
    ("travel_total", "sql", "structured", "grounded", None,
     "SELECT CAST(SUM(amount_usd) AS INTEGER) FROM expenses WHERE category='travel'", [
        "What is the total amount spent on travel?",
        "How much did we spend on travel in total?"]),
    ("most_leave", "sql", "structured", "grounded", None,
     "SELECT name FROM employees ORDER BY leave_days_used DESC LIMIT 1", [
        "Who has used the most leave days?",
        "Which employee has taken the most annual leave?"]),
    ("big_expense", "sql", "structured", "grounded", None,
     "SELECT e.name FROM expenses x JOIN employees e ON e.id=x.employee_id WHERE x.amount_usd > 500", [
        "Which expenses were over $500, and who submitted them?",
        "Who submitted an expense above $500?"]),
    ("ana_leave", "sql", "structured", "grounded", None,
     "SELECT leave_days_used FROM employees WHERE name='Ana Lee'", [
        "How many leave days has Ana Lee used?",
        "How much annual leave has Ana Lee taken so far?"]),
    # ---- hybrid ----
    ("ben_over", "hybrid", "hybrid", "grounded", "Leave_Policy.pdf", ["22", "20"], [
        "Has Ben Ortiz used more annual leave than the policy allows?",
        "Is Ben Ortiz over his leave entitlement?"]),
    ("dana_vp", "hybrid", "hybrid", "grounded", "Travel_and_Expense_Policy.docx", ["1830", "VP"], [
        "Did Dana Kim's travel expense need VP approval?",
        "Was VP sign-off required for Dana Kim's trip?"]),
    ("meal_breach", "hybrid", "hybrid", "grounded", "Travel_and_Expense_Policy.docx", ["Ben"], [
        "Which employees had meal expenses above the policy limit?",
        "Did anyone exceed the meal allowance?"]),
    # ---- not answerable: must be refused ----
    ("ceo_salary", "none", None, "insufficient_evidence", None, [], [
        "What is the CEO's salary?",
        "How much does the CEO earn?"]),
    ("revenue", "none", None, "insufficient_evidence", None, [], [
        "What was the company's revenue last year?",
        "How much money did Brightwave make in 2025?"]),
    ("dress_code", "none", None, "insufficient_evidence", None, [], [
        "What is the dress code?",
        "Can I wear jeans to the office?"]),
]

# How real users wrap the same question
WRAPPERS = ["{q}", "Quick question: {q}", "{q} Thanks!", "Hi, {ql}", "Can you tell me: {ql}",
            "According to company policy, {ql}", "{q} Please cite the source.", "hey {ql}",
            "I need to know: {ql}", "{q} (asking for my team)"]


def truth_from_sql(db: Path, sql: str) -> list[str]:
    with sqlite3.connect(db) as con:
        return [str(row[0]) for row in con.execute(sql).fetchall()]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=10_000)
    p.add_argument("--out", default="tests/eval/questions_10k.jsonl")
    p.add_argument("--db", default="data/sqlite/km.db")
    p.add_argument("--seed", type=int, default=7)
    args = p.parse_args()
    rng = random.Random(args.seed)

    # every (fact, paraphrase, wrapper) combination is one distinct question text
    pool = []
    for fid, group, route, status, source, expect, paraphrases in FACTS:
        if isinstance(expect, str):  # truth_sql
            expect = truth_from_sql(Path(args.db), expect)
        for pi, q in enumerate(paraphrases):
            for wi, w in enumerate(WRAPPERS):
                text = w.format(q=q, ql=q[0].lower() + q[1:])
                pool.append({"intent": fid, "group": group, "route": route, "status": status,
                             "source": source, "expect_in_answer": expect,
                             "paraphrase": pi, "wrapper": wi, "question": text})

    # skewed popularity: intent weight ~ 1/rank (Zipf), like real traffic
    intents = [f[0] for f in FACTS]
    rng.shuffle(intents)
    weight = {fid: 1 / (rank + 1) for rank, fid in enumerate(intents)}
    weights = [weight[r["intent"]] for r in pool]
    rows = rng.choices(pool, weights=weights, k=args.n)

    out = Path(args.out)
    with out.open("w", encoding="utf-8") as f:
        for i, r in enumerate(rows):
            f.write(json.dumps({"id": f"q{i:05d}", **r}) + "\n")
    unique = len({r["question"] for r in rows})
    print(f"Wrote {len(rows)} questions to {out}: {unique} distinct texts, "
          f"{len({r['intent'] for r in rows})} intents (facts), {len(pool)} possible texts")


if __name__ == "__main__":
    main()
