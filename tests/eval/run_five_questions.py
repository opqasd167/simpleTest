"""Ask five questions to the REAL model and print an analysis of each: route, SQL, evidence,
claim-by-claim check, status, and where the time went (per pipeline stage).

    python tests/eval/run_five_questions.py            # needs .env with a working LLM, plus km seed + km ingest
    python tests/eval/run_five_questions.py --only 3,5

The same five questions as tests/integration/test_five_questions.py (the offline, scripted version):
one per path through the pipeline. Each question costs 3-5 LLM calls. Results go to
tests/eval/five_questions_last_run.json.
"""
import argparse
import json
import time
from pathlib import Path

from km.config import get_settings
from km.container import build_llm, build_qa_service
from km.domain.models import Route, Verdict
from km.logging_setup import setup_logging

CHARS_PER_TOKEN = 4  # rough estimate, same as run_scale_eval.py

# question, expected route, expected status, words the answer must contain, what it demonstrates
QUESTIONS = [
    ("What is the daily meal expense limit?", "unstructured", "grounded", ["75"],
     "documents only: no SQL writer call"),
    ("What is the total amount spent on travel?", "structured", "grounded", ["2250"],
     "SQL only: the database does the arithmetic"),
    ("Did Dana Kim's travel expense need VP approval?", "hybrid", "grounded", ["1830", "VP"],
     "SQL runs first; its expense date steers the document search"),
    ("Has Ben Ortiz used more annual leave than the policy allows?", "hybrid", "grounded", ["22", "20"],
     "database fact compared with a policy rule, every claim checked"),
    ("What is the CEO's salary?", None, "insufficient_evidence", [],
     "no evidence -> clear refusal, never a guess"),
]


class StageMeter:
    """Wraps the real LLM and records each call: which stage, how long, how big."""

    def __init__(self, inner):
        self.inner, self.log = inner, []

    def complete(self, system, user):
        return self._timed("write_answer", system + user, lambda: self.inner.complete(system, user))

    def structured(self, system, user, schema):
        stage = {Route: "route", Verdict: "validate"}.get(schema, "write_sql")
        return self._timed(stage, system + user, lambda: self.inner.structured(system, user, schema))

    def _timed(self, stage, prompt, call):
        start = time.perf_counter()
        out = call()
        text = out if isinstance(out, str) else out.model_dump_json()
        self.log.append({"stage": stage, "ms": int((time.perf_counter() - start) * 1000),
                         "in_tokens": len(prompt) // CHARS_PER_TOKEN, "out_tokens": len(text) // CHARS_PER_TOKEN})
        return out


def contains_all(answer: str, expected: list[str]) -> bool:
    text = answer.replace(",", "").lower()  # "$2,250" matches "2250"
    return all(e.replace(",", "").lower() in text for e in expected)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="comma-separated question numbers, e.g. 3,5")
    parser.add_argument("--out", default="tests/eval/five_questions_last_run.json")
    args = parser.parse_args()
    setup_logging("WARNING")

    settings = get_settings()
    meter = StageMeter(build_llm(settings))
    service = build_qa_service(settings, llm=meter)
    wanted = {int(n) for n in args.only.split(",")} if args.only else set(range(1, 6))

    rows = []
    for i, (question, route, status, expect, shows) in enumerate(QUESTIONS, 1):
        if i not in wanted:
            continue
        meter.log = []
        r = service.ask(question)
        checks = {"route": route is None or (r.route is not None and r.route.intent == route),
                  "status": r.status == status,
                  "answer": contains_all(r.answer, expect)}
        llm_ms = sum(c["ms"] for c in meter.log)

        print(f"\n=== Q{i}. {question}\n    shows:    {shows}")
        print(f"    route:    {r.route.intent if r.route else '-'}  ({r.route.reason if r.route else ''})")
        print(f"    sql:      {r.sql or '-'}")
        for e in r.evidence:
            print(f"    evidence: [{e.tag}] {e.label[:100]}")
        for c in (r.verdict.claims if r.verdict else []):
            print(f"    claim:    [{'OK' if c.supported else 'NO'} {c.evidence_tag}] {c.claim}")
        print(f"    status:   {r.status}")
        print(f"    answer:   {r.answer}")
        print(f"    time:     {r.latency_ms} ms total, {llm_ms} ms in {len(meter.log)} LLM calls, "
              f"{r.latency_ms - llm_ms} ms retrieval + code")
        for c in meter.log:
            print(f"              {c['stage']:<13}{c['ms']:>7} ms  ~{c['in_tokens']} in / ~{c['out_tokens']} out tokens")
        print("    checks:   " + "  ".join(f"{k} {'PASS' if v else 'FAIL'}" for k, v in checks.items()))
        rows.append({"n": i, "question": question, "checks": checks, "calls": meter.log,
                     "result": r.model_dump()})

    if not rows:
        return
    print(f"\n{'#':<4}{'route':<14}{'status':<23}{'calls':>6}{'ms':>8}  checks")
    for row in rows:
        r = row["result"]
        intent = r["route"]["intent"] if r["route"] else "-"
        passed = sum(row["checks"].values())
        print(f"Q{row['n']:<3}{intent:<14}{r['status']:<23}{len(row['calls']):>6}{r['latency_ms']:>8}  {passed}/3")
    all_pass = sum(all(row["checks"].values()) for row in rows)
    calls = sum(len(row["calls"]) for row in rows)
    tokens = sum(c["in_tokens"] + c["out_tokens"] for row in rows for c in row["calls"])
    print(f"\nProvider {settings.llm_provider}: {all_pass}/{len(rows)} questions fully correct, "
          f"{calls} LLM calls, ~{tokens} tokens")

    Path(args.out).write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    print(f"Details written to {args.out}")


if __name__ == "__main__":
    main()
