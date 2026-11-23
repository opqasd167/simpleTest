"""Tiered evaluation for large question sets (thousands of questions).

Tiers, cheapest first. Run the cheap ones on everything, the expensive one on a sample:
  retrieval  0 LLM calls/question   is the expected document in the top-k chunks?
  route      1 LLM call/question    does the router pick the expected route?
  full       2-4 LLM calls/question whole pipeline: expected status + expected facts

Usage (from the project root):
  python tests/eval/run_scale_eval.py plan      --questions tests/eval/questions_10k.jsonl
  python tests/eval/run_scale_eval.py retrieval --questions tests/eval/questions_10k.jsonl
  python tests/eval/run_scale_eval.py route     --questions ... --sample per-intent --workers 4
  python tests/eval/run_scale_eval.py full      --questions ... --sample per-intent --workers 4

--sample: all | distinct | per-intent | <N>   (N = stratified random sample of distinct texts)
Results are appended to tests/eval/runs/<tier>.jsonl; finished ids are skipped on re-run (resumable).
"""
import argparse
import json
import math
import random
import statistics
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from km.config import get_settings
from km.container import build_llm, build_qa_service
from km.llm.metered import MeteredLLM
from km.logging_setup import setup_logging
from km.observability import flush, trace_attributes
from km.routing.intent_router import IntentRouter
from km.storage.sql_store import SqlStore
from km.storage.vector_store import VectorStore

RUNS = Path("tests/eval/runs")
# USD per million tokens (input, output); Message Batches API = 50% of these
PRICES = {"claude-opus-5-5": (4.00, 20.00), "claude-sonnet-5-5": (2.00, 10.00),
          "claude-haiku-5-5": (0.10, 0.50)}
CHARS_PER_TOKEN = 4  # rough average for English text


# ---------------------------------------------------------------- data
def load(path: str) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def distinct(rows: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in rows:
        key = " ".join(r["question"].lower().split())
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def sample(rows: list[dict], how: str, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    uniq = distinct(rows)
    if how == "all":
        return rows
    if how == "distinct":
        return uniq
    by_intent = defaultdict(list)
    for r in uniq:
        by_intent[r["intent"]].append(r)
    if how == "per-intent":  # one random wording of every intent: full coverage, minimum cost
        return [rng.choice(v) for _, v in sorted(by_intent.items())]
    n = int(how)  # stratified by group, proportional, at least 1 per group
    by_group = defaultdict(list)
    for r in uniq:
        by_group[r["group"]].append(r)
    out = []
    for g, items in sorted(by_group.items()):
        k = max(1, round(n * len(items) / len(uniq)))
        out += rng.sample(items, min(k, len(items)))
    return out


def wilson(passed: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% confidence interval for a pass rate."""
    if n == 0:
        return (0.0, 0.0)
    p = passed / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def contains_all(answer: str, expected: list[str]) -> bool:
    text = answer.replace(",", "").lower()
    return all(e.replace(",", "").lower() in text for e in expected)


# ---------------------------------------------------------------- tiers
def check_retrieval(store: VectorStore, k: int):
    def run(r):
        if not r.get("source"):
            return None  # SQL-only or unanswerable: no document to find
        hits = store.search(r["question"], k)
        return {"passed": any(h.source == r["source"] for h in hits),
                "top1": bool(hits) and hits[0].source == r["source"],
                "got": [h.source for h in hits]}
    return run


def check_route(router: IntentRouter, schema: str):
    def run(r):
        if r["route"] is None:
            return None  # unanswerable: any route is acceptable, the full tier checks refusal
        route = router.route(r["question"], schema)
        return {"passed": route.intent == r["route"], "got": route.intent}
    return run


def check_full(service):
    def run(r):
        res = service.ask(r["question"])
        ok = res.status == r["status"] and contains_all(res.answer, r["expect_in_answer"])
        return {"passed": ok, "got": res.status, "answer": res.answer[:300],
                "latency_ms": res.latency_ms}
    return run


def execute(tier: str, rows: list[dict], fn, workers: int) -> list[dict]:
    RUNS.mkdir(parents=True, exist_ok=True)
    out_path = RUNS / f"{tier}.jsonl"
    done = {json.loads(line)["id"] for line in out_path.read_text(encoding="utf-8").splitlines()
            if line} if out_path.exists() else set()
    todo = [r for r in rows if r["id"] not in done]
    print(f"{tier}: {len(rows)} questions, {len(done & {r['id'] for r in rows})} already done, "
          f"running {len(todo)} with {workers} worker(s)", flush=True)

    def one(r):
        start = time.perf_counter()
        try:
            res = fn(r)
        except Exception as e:  # one bad question must not stop a 10k run
            res = {"passed": False, "got": f"error: {e}"[:200]}
        if res is None:
            return None
        return {"id": r["id"], "intent": r["intent"], "group": r["group"],
                "question": r["question"], "seconds": round(time.perf_counter() - start, 2), **res}

    results = []
    with out_path.open("a", encoding="utf-8") as f, ThreadPoolExecutor(workers) as pool:
        futures = [pool.submit(one, r) for r in todo]
        for i, fut in enumerate(as_completed(futures), 1):
            rec = fut.result()
            if rec:
                f.write(json.dumps(rec) + "\n")
                f.flush()  # resumable: every finished question is on disk
                results.append(rec)
            if i % max(1, len(todo) // 10) == 0:
                print(f"  {i}/{len(todo)}", flush=True)
    wanted = {r["id"] for r in rows}
    return [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines()
            if line and json.loads(line)["id"] in wanted]


# ---------------------------------------------------------------- report
def report(tier: str, results: list[dict], wall: float, metered: MeteredLLM | None,
           grok, workers: int, all_rows: list[dict]) -> dict:
    print(f"\n=== {tier} tier: {len(results)} scored questions ===")
    by_group = defaultdict(list)
    for r in results:
        by_group[r["group"]].append(r["passed"])
    groups = {}
    for g, vals in sorted(by_group.items()) + [("ALL", [r["passed"] for r in results])]:
        lo, hi = wilson(sum(vals), len(vals))
        groups[g] = {"n": len(vals), "passed": sum(vals), "rate": sum(vals) / len(vals),
                     "ci95": [round(lo, 3), round(hi, 3)]}
        print(f"  {g:7} {sum(vals):5}/{len(vals):<5} {100 * sum(vals) / len(vals):5.1f}%  "
              f"95% CI {100 * lo:5.1f}-{100 * hi:5.1f}%")
    if tier == "retrieval":
        top1 = [r.get("top1", False) for r in results]
        lo, hi = wilson(sum(top1), len(top1))
        groups["ALL"]["top1_rate"] = round(sum(top1) / len(top1), 3)
        print(f"  hit@1   {sum(top1):5}/{len(top1):<5} {100 * sum(top1) / len(top1):5.1f}%  "
              f"95% CI {100 * lo:5.1f}-{100 * hi:5.1f}%   (expected document ranked first)")
        miss1 = Counter(r["intent"] for r in results if not r.get("top1"))
        summary_top1 = miss1.most_common(5)
        print(f"  most hit@1 misses by intent: {summary_top1}")
    fails = [r for r in results if not r["passed"]]
    for r in fails[:8]:
        print(f"  FAIL [{r['intent']}] got={r['got']}  q={r['question'][:70]}")
    summary = {"tier": tier, "scored": len(results), "groups": groups, "wall_seconds": round(wall, 1),
               "workers": workers, "failed_intents": Counter(r["intent"] for r in fails).most_common()}

    secs = [r["seconds"] for r in results]
    if secs:
        q = statistics.quantiles(secs, n=20) if len(secs) > 1 else [secs[0]] * 19
        summary["latency_s"] = {"p50": round(statistics.median(secs), 2), "p95": round(q[18], 2)}
        print(f"  latency per question: p50 {summary['latency_s']['p50']} s, "
              f"p95 {summary['latency_s']['p95']} s; wall {wall:.0f} s with {workers} workers")

    if metered and metered.calls:
        n = len(results)
        per_q = {"calls": metered.calls / n,
                 "in_tokens": metered.in_chars / CHARS_PER_TOKEN / n,
                 "out_tokens": (grok.total_output_tokens / n) if grok and grok.calls
                 else metered.out_chars / CHARS_PER_TOKEN / n}
        summary["per_question"] = {k: round(v, 1) for k, v in per_q.items()}
        print(f"  per question: {per_q['calls']:.1f} LLM calls, ~{per_q['in_tokens']:.0f} input tokens, "
              f"~{per_q['out_tokens']:.0f} output tokens (incl. reasoning)")
        if grok and grok.calls:
            summary["grok_usd_per_question"] = round(grok.total_cost_usd / n, 4)
            print(f"  measured Grok CLI cost: ${grok.total_cost_usd:.2f} total, "
                  f"${grok.total_cost_usd / n:.4f} per question")
        summary["projection"] = project(per_q, summary, all_rows, wall / max(n, 1) * workers, workers)
    return summary


def project(per_q: dict, summary: dict, all_rows: list[dict], sec_per_q: float, workers: int) -> dict:
    scenarios = {"all rows": len(all_rows), "distinct texts": len(distinct(all_rows)),
                 "per-intent sample": len({r["intent"] for r in all_rows}),
                 "stratified 500": min(500, len(distinct(all_rows)))}
    print("\n  Projection (USD; Claude = list price from token estimates, batch = 50% off):")
    header = f"  {'scenario':18} {'questions':>9} {'LLM calls':>9} {'Grok CLI':>9}" + "".join(
        f"{m.replace('claude-', ''):>12}" for m in PRICES) + f"{'opus batch':>11} {'hours@' + str(workers):>9}"
    print(header)
    out = {}
    for name, n in scenarios.items():
        row = {"questions": n, "calls": round(per_q["calls"] * n)}
        if "grok_usd_per_question" in summary:
            row["grok"] = round(summary["grok_usd_per_question"] * n, 2)
        for m, (pin, pout) in PRICES.items():
            row[m] = round(n * (per_q["in_tokens"] * pin + per_q["out_tokens"] * pout) / 1e6, 2)
        row["claude-opus-5-5 batch"] = round(row["claude-opus-5-5"] / 2, 2)
        row["hours"] = round(n * sec_per_q / workers / 3600, 2)
        out[name] = row
        print(f"  {name:18} {n:>9} {row['calls']:>9} {row.get('grok', 0):>9.2f}" + "".join(
            f"{row[m]:>12.2f}" for m in PRICES) + f"{row['claude-opus-5-5 batch']:>11.2f} {row['hours']:>9.2f}")
    return out


# ---------------------------------------------------------------- main
def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("tier", choices=["plan", "retrieval", "route", "full"])
    p.add_argument("--questions", default="tests/eval/questions_10k.jsonl")
    p.add_argument("--sample", default=None, help="all | distinct | per-intent | N")
    p.add_argument("--workers", type=int, default=1)
    args = p.parse_args()
    setup_logging("WARNING")

    rows = load(args.questions)
    uniq = distinct(rows)
    print(f"{len(rows)} rows, {len(uniq)} distinct texts, {len({r['intent'] for r in rows})} intents; "
          f"top intents by traffic: {Counter(r['intent'] for r in rows).most_common(3)}")
    if args.tier == "plan":
        for name, n in [("all rows", len(rows)), ("distinct", len(uniq)),
                        ("per-intent", len({r['intent'] for r in rows}))]:
            print(f"  {name:11} {n:6} questions -> retrieval 0 calls, route {n} calls, full ~{3.5 * n:.0f} calls")
        return

    s = get_settings()
    chosen = sample(rows, args.sample or ("distinct" if args.tier == "retrieval" else "per-intent"))
    metered, grok, start = None, None, time.perf_counter()
    if args.tier == "retrieval":
        fn = check_retrieval(VectorStore(s.chroma_dir, s.chroma_collection), s.top_k)
    else:
        inner = build_llm(s)
        grok = inner if hasattr(inner, "total_cost_usd") else None
        metered = MeteredLLM(inner)
        if args.tier == "route":
            fn = check_route(IntentRouter(metered), SqlStore(s.sqlite_path).schema())
        else:
            fn = check_full(build_qa_service(s, llm=metered))
    with trace_attributes(session_id=f"scale-{args.tier}-{int(time.time())}", tags=["eval", args.tier]):
        results = execute(args.tier, chosen, fn, args.workers)
    flush()
    summary = report(args.tier, results, time.perf_counter() - start, metered, grok, args.workers, rows)
    (RUNS / f"{args.tier}_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
