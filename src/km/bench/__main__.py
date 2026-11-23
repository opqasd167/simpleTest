"""python -m km.bench run | compare | list | harvest   (run from the project root)"""
import argparse
import json
import sys
from pathlib import Path

from km.bench.dataset import load_cases, select
from km.bench.harvest import harvest
from km.bench.report import compare, list_runs, resolve
from km.bench.runner import STAGES, run_benchmark
from km.config import get_settings
from km.logging_setup import setup_logging


def check_thresholds(run: Path, spec: str) -> list[str]:
    """'retrieval=0.9,e2e=0.85' -> list of failures (empty = all thresholds met)."""
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    failures = []
    for item in spec.split(","):
        stage, minimum = item.split("=")
        st = summary["stages"].get(stage.strip())
        if st is None:
            failures.append(f"{stage}: stage was not run")
        elif st["overall"]["rate"] < float(minimum):
            failures.append(f"{stage}: {st['overall']['rate']:.3f} < {float(minimum):.3f}")
    return failures


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m km.bench")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run benchmark stages and save a run folder")
    r.add_argument("--corpus", default="benchmarks/corpora/v2")
    r.add_argument("--stages", default="retrieval", help=f"comma list of {','.join(STAGES)}")
    r.add_argument("--ids", help="only these case ids, e.g. H01,H04")
    r.add_argument("--category", help="only these categories, e.g. hybrid,adversarial")
    r.add_argument("--tags", help="only cases with any of these tags, e.g. versioning,regional")
    r.add_argument("--workers", type=int, default=3)
    r.add_argument("--repeat", type=int, default=1, help="run LLM stages N times to measure flakiness")
    r.add_argument("--judge", action="store_true",
                   help="also grade e2e answers against reference answers (KM_JUDGE_PROVIDER/KM_JUDGE_MODEL)")
    r.add_argument("--rebuild", action="store_true", help="re-seed and re-index the corpus")
    r.add_argument("--label", default="", help="short tag appended to the run folder name")
    r.add_argument("--fail-under", help="exit 1 if a stage pass rate is below, e.g. retrieval=0.9,e2e=0.85")
    c = sub.add_parser("compare", help="compare two runs (folder name, prefix, or path)")
    c.add_argument("a")
    c.add_argument("b")
    sub.add_parser("list", help="list saved runs")
    h = sub.add_parser("harvest", help="turn the question log into draft cases for review")
    h.add_argument("--log", default="data/logs/questions.jsonl")
    h.add_argument("--corpus", default="benchmarks/corpora/v2")
    h.add_argument("--all", action="store_true", help="draft every new question, not only failures")
    args = ap.parse_args()
    setup_logging("WARNING")

    if args.cmd == "run":
        corpus = Path(args.corpus)
        stages = [s.strip() for s in args.stages.split(",")]
        unknown = set(stages) - set(STAGES)
        if unknown:
            raise SystemExit(f"Unknown stage(s): {unknown}")
        cases = select(load_cases(corpus / "dataset.jsonl"), args.ids, args.category, args.tags)
        out = run_benchmark(corpus, cases, stages, get_settings(), args.workers, args.repeat,
                            args.judge, args.rebuild, args.label)
        print(f"\nSaved {out}\n")
        print((out / "report.md").read_text(encoding="utf-8"))
        if args.fail_under:
            failures = check_thresholds(out, args.fail_under)
            if failures:
                print("THRESHOLDS NOT MET: " + "; ".join(failures))
                sys.exit(1)
            print(f"Thresholds met: {args.fail_under}")
    elif args.cmd == "compare":
        print(compare(resolve(args.a), resolve(args.b)))
    elif args.cmd == "harvest":
        corpus = Path(args.corpus)
        out = corpus / "candidates.jsonl"
        n = harvest(Path(args.log), corpus / "dataset.jsonl", out, args.all)
        print(f"{n} draft case(s) appended to {out}. Review each one, fill in the expected result, "
              f"remove the needs_review tag and move it into dataset.jsonl.")
    else:
        print(list_runs())


if __name__ == "__main__":
    main()
