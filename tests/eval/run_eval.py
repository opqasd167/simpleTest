"""End-to-end evaluation against a real LLM backend.
Run from the project root:  python tests/eval/run_eval.py [--only U1,H2]
Each question makes 2-4 LLM calls, so a full run costs real tokens."""
import argparse
import json
from datetime import datetime
from pathlib import Path

from km.config import get_settings
from km.container import build_qa_service
from km.logging_setup import setup_logging
from km.observability import flush, trace_attributes


def contains_all(answer: str, expected: list[str]) -> bool:
    text = answer.replace(",", "").lower()  # "$2,250" matches "2250"
    return all(e.replace(",", "").lower() in text for e in expected)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="comma-separated question ids, e.g. U1,H2")
    parser.add_argument("--out", default="tests/eval/last_run.json")
    args = parser.parse_args()
    setup_logging("WARNING")

    cases = json.loads(Path("tests/eval/questions.json").read_text(encoding="utf-8"))
    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if c["id"] in wanted]
    settings = get_settings()
    service = build_qa_service(settings)
    run_id = datetime.now().strftime("eval-%Y%m%d-%H%M")

    results = []
    with trace_attributes(session_id=run_id, tags=["eval"]):  # one Langfuse session per run
        for c in cases:
            r = service.ask(c["question"])
            results.append((c, r))
            intent = r.route.intent if r.route else "-"
            print(f"{c['id']:3} {r.status:22} {intent:13} {r.latency_ms:6} ms  {c['question']}",
                  flush=True)
    flush()

    route_ok = [r.route is not None and r.route.intent == c["route"] for c, r in results if c["route"]]
    status_ok = [r.status == c["status"] for c, r in results]
    answer_ok = [contains_all(r.answer, c["expect_in_answer"]) for c, r in results if c["expect_in_answer"]]
    latency = sorted(r.latency_ms for _, r in results)

    print(f"\nProvider:        {settings.llm_provider}")
    print(f"Route accuracy:  {sum(route_ok)}/{len(route_ok)}")
    print(f"Expected status: {sum(status_ok)}/{len(status_ok)}")
    print(f"Answer contains: {sum(answer_ok)}/{len(answer_ok)}")
    print(f"Latency: median {latency[len(latency) // 2]} ms, max {latency[-1]} ms")

    Path(args.out).write_text(json.dumps(
        [{"case": c, "result": r.model_dump()} for c, r in results], indent=2), encoding="utf-8")
    print(f"Details written to {args.out}")


if __name__ == "__main__":
    main()
