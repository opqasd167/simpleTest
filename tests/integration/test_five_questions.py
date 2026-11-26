"""Five questions, five paths through the pipeline: a walkthrough you can run and explain.

    pytest tests/integration/test_five_questions.py -v -s     # -s prints the analysis of each question

Offline and deterministic: a ScriptedLLM plays the model, so every run gives the same result
and costs nothing. Everything else is the real code: QAService, SqlRetriever + sql_guard on the
seeded SQLite database, retrieval hints, the AnswerWriter and the GroundednessValidator's relabel.

    #  Question                                          Route          Path shown            LLM calls
    1  What is the daily meal expense limit?              unstructured   documents only        3
    2  What is the total amount spent on travel?          structured     SQL only              4
    3  Did Dana Kim's travel expense need VP approval?    hybrid         SQL steers doc search 4
    4  Has Ben Ortiz used more annual leave than ...?     hybrid         unsupported claim cut 4
    5  What is the CEO's salary?                          structured     bad SQL -> refusal    3

"LLM calls" is the main performance number: each call is one round trip to the model, so it sets
both the latency and the token cost of a question. Questions 1 and 5 show where the pipeline saves
calls (no SQL writer for a policy question; no writer or validator when there is no evidence).
Run tests/eval/run_five_questions.py to ask the same five questions to the real model.
"""
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from km.domain.models import AskResult, Claim, DocChunk, Route, Verdict
from km.generation.answer_writer import AnswerWriter
from km.retrieval.sql_retriever import SqlRetriever
from km.routing.intent_router import IntentRouter
from km.services.qa_service import NO_ANSWER, QAService
from km.storage.sql_store import SqlStore
from km.validation.groundedness import GroundednessValidator

# Real text from data/raw/docs, as the vector store would return it.
MEALS = DocChunk(source="Travel_and_Expense_Policy.docx", location="table 1",
                 text="Meals | $75 per person per day | Line manager",
                 meta={"status": "current", "effective_from": 20260101})
TRAVEL = DocChunk(source="Travel_and_Expense_Policy.docx", location="table 1",
                  text="Travel (flights, trains, car hire) | Over $1,500 per trip | "
                       "Vice President (VP), before booking",
                  meta={"status": "current", "effective_from": 20260101})
LEAVE = DocChunk(source="Leave_Policy.pdf", location="page 1",
                 text="Annual leave depends on length of service, measured on 1 January of the leave "
                      "year: Less than 3 years: 20 working days. 3 years or more: 25 working days.",
                 meta={"status": "current", "effective_from": 20260101})


@dataclass
class Script:
    """What the model 'says' at each stage for one question."""
    route: str
    answer: str = ""
    sql: list[str] = field(default_factory=list)   # one entry per SQL attempt (2nd = self-correction)
    claims: list[tuple[str, bool, str]] = field(default_factory=list)
    llm_label: str = "grounded"                    # the label the model claims; code recomputes it


class ScriptedLLM:
    """Plays the model and logs each call by pipeline stage, like MeteredLLM does for the real one."""

    def __init__(self, script: Script):
        self.s, self.calls, self.prompts = script, [], {}
        self._sql = iter(script.sql)

    def complete(self, system, user):
        self._log("write_answer", user)
        return self.s.answer

    def structured(self, system, user, schema):
        if schema is Route:
            self._log("route", user)
            return Route(intent=self.s.route, reason=f"scripted: {self.s.route}")
        if schema is Verdict:
            self._log("validate", user)
            return Verdict(claims=[Claim(claim=c, supported=ok, evidence_tag=tag)
                                   for c, ok, tag in self.s.claims], verdict=self.s.llm_label)
        self._log("write_sql", user)
        return schema(sql=next(self._sql))

    def _log(self, stage, user):
        self.calls.append(stage)
        self.prompts.setdefault(stage, []).append(user)


class KeywordDocs:
    """Stands in for Chroma: returns the chunks whose keyword appears in the question.
    Records the hints the pipeline passes, to show SQL facts steering document search."""

    def __init__(self):
        self.hints = None

    def retrieve(self, question, hints=None):
        self.hints = hints
        q = question.lower()
        return [c for key, c in (("meal", MEALS), ("travel", TRAVEL), ("leave", LEAVE)) if key in q]


@dataclass
class Run:
    result: AskResult
    llm: ScriptedLLM
    docs: KeywordDocs


@pytest.fixture
def ask(tmp_path):
    store = SqlStore(tmp_path / "km.db")
    store.init_from_script(Path("data/seed/seed.sql"))

    def _ask(question: str, script: Script) -> Run:
        llm, docs = ScriptedLLM(script), KeywordDocs()
        service = QAService(IntentRouter(llm), docs, SqlRetriever(llm, store, 50),
                            AnswerWriter(llm), GroundednessValidator(llm), store)
        run = Run(service.ask(question), llm, docs)
        print(analysis(run))
        return run
    return _ask


def analysis(run: Run) -> str:
    """A readable report of one question: what happened at each stage, and what it cost."""
    r = run.result
    lines = [f"\n=== {r.question}",
             f"route     {r.route.intent if r.route else '-'}",
             f"sql       {r.sql or '-'}",
             f"evidence  {', '.join(e.tag + ': ' + e.label for e in r.evidence) or 'none'}"]
    if run.docs.hints:
        lines.append(f"hints     regions={sorted(run.docs.hints.regions)} years={sorted(run.docs.hints.years)}")
    for c in (r.verdict.claims if r.verdict else []):
        lines.append(f"claim     [{'OK' if c.supported else 'NO'} {c.evidence_tag}] {c.claim}")
    lines += [f"status    {r.status}",
              f"llm calls {len(run.llm.calls)}  ({' -> '.join(run.llm.calls)})",
              f"answer    {r.answer}"]
    return "\n".join(lines)


# ---- 1. Documents only ---------------------------------------------------------------------------

def test_q1_policy_question_reads_documents_only(ask):
    run = ask("What is the daily meal expense limit?", Script(
        route="unstructured",
        answer="The meal limit is $75 per person per day, approved by the line manager [D1].",
        claims=[("The meal limit is $75 per person per day", True, "D1"),
                ("Meals are approved by the line manager", True, "D1")]))

    assert run.result.status == "grounded"
    assert run.result.sql is None                                   # the database is never queried
    assert run.result.sources == ["Travel_and_Expense_Policy.docx (table 1)"]
    assert run.llm.calls == ["route", "write_answer", "validate"]   # no SQL writer: one call saved
    assert "[D1]" in run.llm.prompts["write_answer"][0]             # writer saw the tagged chunk


# ---- 2. SQL only --------------------------------------------------------------------------------

def test_q2_count_question_reads_the_database_only(ask):
    run = ask("What is the total amount spent on travel?", Script(
        route="structured",
        sql=["SELECT SUM(amount_usd) AS total FROM expenses WHERE category = 'travel'"],
        answer="Total travel spend is $2,250 [SQL].",
        claims=[("Total travel spend is $2,250", True, "SQL")]))

    assert run.result.status == "grounded"
    assert run.result.sources == []                                 # no document search
    sql_item = next(e for e in run.result.evidence if e.tag == "SQL")
    assert '"total": 2250.0' in sql_item.text                       # 420 + 1830, computed by SQLite
    assert run.llm.calls == ["route", "write_sql", "write_answer", "validate"]


# ---- 3. Hybrid: SQL runs first and steers document search ---------------------------------------

def test_q3_hybrid_question_uses_sql_facts_to_pick_the_policy(ask):
    run = ask("Did Dana Kim's travel expense need VP approval?", Script(
        route="hybrid",
        sql=["SELECT e.name, x.amount_usd, x.expense_date FROM expenses x "
             "JOIN employees e ON e.id = x.employee_id "
             "WHERE e.name = 'Dana Kim' AND x.category = 'travel'"],
        answer="Yes. Dana Kim's travel expense was $1,830 [SQL], and trips over $1,500 need "
               "VP approval before booking [D1].",
        claims=[("Dana Kim's travel expense was $1,830", True, "SQL"),
                ("Trips over $1,500 need VP approval before booking", True, "D1")]))

    assert run.result.status == "grounded"
    assert run.docs.hints.years == {2026}                           # expense_date 2026-10-01 -> 2026 policy
    assert [e.tag for e in run.result.evidence] == ["D1", "SQL"]    # both sources reach the writer
    assert run.llm.calls == ["route", "write_sql", "write_answer", "validate"]


# ---- 4. Hybrid: the validator removes a claim the evidence does not support ---------------------

def test_q4_unsupported_claim_is_removed(ask):
    run = ask("Has Ben Ortiz used more annual leave than the policy allows?", Script(
        route="hybrid",
        sql=["SELECT name, hire_date, leave_days_used FROM employees WHERE name = 'Ben Ortiz'"],
        answer="Ben Ortiz has used 22 days [SQL]. With under 3 years of service he is entitled to "
               "20 days [D1], so he is 2 days over. He will lose his annual bonus.",
        claims=[("Ben Ortiz has used 22 days of annual leave", True, "SQL"),
                ("With under 3 years of service the entitlement is 20 days", True, "D1"),
                ("He will lose his annual bonus", False, "none")],   # nothing in the evidence says this
        llm_label="grounded"))                                     # the model's label is wrong ...

    assert run.result.verdict.verdict == "partially_grounded"      # ... code recomputes it from claims
    assert run.result.status == "partial"
    assert "22 days" in run.result.answer and "20 days" in run.result.answer
    assert "bonus" not in run.result.answer                        # the user never sees the guess
    assert "(Unsupported statements were removed.)" in run.result.answer


# ---- 5. No evidence: bad SQL is retried once, then the pipeline refuses -------------------------

def test_q5_unanswerable_question_is_refused_without_guessing(ask):
    run = ask("What is the CEO's salary?", Script(
        route="structured",
        sql=["SELECT salary FROM employees WHERE role = 'CEO'",          # no such column
             "SELECT salary_usd FROM employees WHERE role = 'CEO'"],     # self-correction also fails
        answer="The CEO earns $400,000."))                              # must never be shown

    assert run.result.status == "insufficient_evidence"
    assert run.result.answer == NO_ANSWER
    assert run.result.evidence == []
    assert run.llm.calls == ["route", "write_sql", "write_sql"]     # writer and validator skipped
    retry_prompt = run.llm.prompts["write_sql"][1]                 # the model is shown its own error
    assert "Database error: no such column: salary" in retry_prompt


# ---- Summary: the five questions as one table -----------------------------------------------------

def test_summary_of_all_five(ask):
    """One table for the whole walkthrough: route, status and LLM calls per question."""
    cases = [
        ("What is the daily meal expense limit?", Script(
            route="unstructured", answer="$75 per day [D1].", claims=[("$75 per day", True, "D1")])),
        ("What is the total amount spent on travel?", Script(
            route="structured", answer="$2,250 [SQL].", claims=[("$2,250", True, "SQL")],
            sql=["SELECT SUM(amount_usd) AS total FROM expenses WHERE category = 'travel'"])),
        ("Did Dana Kim's travel expense need VP approval?", Script(
            route="hybrid", answer="Yes, $1,830 [SQL] > $1,500 [D1].",
            claims=[("$1,830", True, "SQL"), ("over $1,500 needs VP", True, "D1")],
            sql=["SELECT amount_usd, expense_date FROM expenses WHERE employee_id = 4"])),
        ("Has Ben Ortiz used more annual leave than the policy allows?", Script(
            route="hybrid", answer="22 days [SQL] vs 20 [D1]; he loses his bonus.",
            claims=[("22 days", True, "SQL"), ("20 days allowed", True, "D1"), ("loses bonus", False, "none")],
            sql=["SELECT leave_days_used FROM employees WHERE id = 2"])),
        ("What is the CEO's salary?", Script(
            route="structured", sql=["SELECT salary FROM employees", "SELECT pay FROM employees"])),
    ]
    runs = [ask(q, s) for q, s in cases]

    print(f"\n{'#':<3}{'route':<14}{'status':<23}{'calls':>5}  question")
    for i, run in enumerate(runs, 1):
        r = run.result
        print(f"{i:<3}{r.route.intent:<14}{r.status:<23}{len(run.llm.calls):>5}  {r.question}")
    total = sum(len(run.llm.calls) for run in runs)
    print(f"total LLM calls: {total} for 5 questions (stages a question does not need are skipped)")

    assert [r.result.status for r in runs] == [
        "grounded", "grounded", "grounded", "partial", "insufficient_evidence"]
    assert [len(r.llm.calls) for r in runs] == [3, 4, 4, 4, 3]
    assert total == 18
