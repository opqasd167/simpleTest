"""Markdown report for one run, comparison of two runs, and a list of saved runs."""
import json
from pathlib import Path

from km.bench.runner import RUNS_DIR


def _load(run: Path) -> tuple[dict, list[dict]]:
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    results = [json.loads(line) for line in (run / "results.jsonl").read_text(encoding="utf-8").splitlines()
               if line]
    return summary, results


def resolve(run: str) -> Path:
    """Accept a full path, a run folder name, or a unique prefix of one."""
    p = Path(run)
    if p.is_dir():
        return p
    matches = sorted(d for d in RUNS_DIR.iterdir() if d.name.startswith(run)) if RUNS_DIR.exists() else []
    if len(matches) != 1:
        raise SystemExit(f"Run '{run}' matched {len(matches)} folders in {RUNS_DIR}")
    return matches[0]


def _pct(block: dict) -> str:
    lo, hi = block["ci95"]
    return f"{block['passed']}/{block['n']} ({100 * block['rate']:.0f}%, CI {100 * lo:.0f}-{100 * hi:.0f}%)"


def render_report(run: Path) -> str:
    summary, results = _load(run)
    cfg = summary["config"]
    llm = cfg["llm"] or {}
    lines = [f"# Benchmark run {cfg['run_id']}", "",
             f"- Corpus: `{cfg['corpus']}` (fingerprint {cfg['corpus_fingerprint']}, dataset {cfg['dataset_sha']}, "
             f"{cfg['cases']} cases)",
             f"- LLM: {llm.get('provider', '-')} / {llm.get('model', '-')} / effort {llm.get('effort') or 'default'}",
             f"- Retrieval: top_k {cfg['retrieval']['top_k']}, chunks {cfg['retrieval']['chunk_size']}"
             f"/{cfg['retrieval']['chunk_overlap']}; prompts {cfg['prompts_sha']}; git {cfg['git']['commit']}"
             f"{' (uncommitted changes)' if cfg['git']['dirty'] else ''}",
             f"- Repeat {cfg['repeat']}, workers {cfg['workers']}, judge {cfg['judge']}", "",
             "## Headline", "", "| Stage | Pass (95% CI) | Extra | Time | LLM calls | Cost |",
             "| --- | --- | --- | --- | --- | --- |"]
    for stage, st in summary["stages"].items():
        extra = ""
        if stage == "retrieval":
            extra = f"hit@1 {st['hit_at_1']:.2f}, MRR {st['mrr']:.2f}, all gold sources {st['all_gold_sources_found']:.2f}"
        elif "outcomes" in st:
            extra = ", ".join(f"{k} {v}" for k, v in st["outcomes"].items())
        if "judge" in st:
            extra += f"; judge {_pct(st['judge'])}"
        cost = st.get("cost") or {}
        usd = f"${cost['usd']:.2f}" if cost.get("usd") else "-"
        lines.append(f"| {stage} | {_pct(st['overall'])} | {extra} | {st['wall_seconds']:.0f} s "
                     f"(p50 {st['seconds_per_case']['p50']} s) | {cost.get('llm_calls', 0)} | {usd} |")
    for stage, st in summary["stages"].items():
        lines += ["", f"## {stage}: by category", "", "| Category | Pass |", "| --- | --- |"]
        lines += [f"| {k} | {_pct(v)} |" for k, v in st["by_category"].items()]
        if st["by_tag"]:
            lines += ["", "| Tag | Pass |", "| --- | --- |"] + [f"| {k} | {_pct(v)} |" for k, v in st["by_tag"].items()]
        if st["flaky_cases"]:
            lines += ["", f"Flaky across repeats: {', '.join(st['flaky_cases'])}"]
        fails = [r for r in results if r["stage"] == stage and not r["passed"] and r["repeat"] == 0]
        if fails:
            lines += ["", f"### {stage}: failures", ""]
            for r in sorted(fails, key=lambda r: r["case_id"]):
                detail = {k: r[k] for k in ("outcome", "got", "rank", "missing", "forbidden", "status", "route",
                                            "error", "sql", "rows", "gold_rows") if k in r and r[k] not in (None, [], "")}
                lines.append(f"- **{r['case_id']}** `{json.dumps(detail, ensure_ascii=False)[:600]}`")
                if r.get("answer"):
                    lines.append(f"  - answer: {r['answer'][:400].replace(chr(10), ' ')}")
    return "\n".join(lines) + "\n"


def compare(a: Path, b: Path) -> str:
    sa, ra = _load(a)
    sb, rb = _load(b)
    out = [f"Comparing A = {a.name}", f"       to B = {b.name}", ""]
    for key in ("corpus_fingerprint", "dataset_sha", "prompts_sha", "code_sha", "scoring_version", "llm",
                "retrieval"):
        if sa["config"].get(key) != sb["config"].get(key):
            out.append(f"  changed {key}: {sa['config'].get(key)} -> {sb['config'].get(key)}")
    if sa["config"].get("scoring_version") != sb["config"].get("scoring_version"):
        out.append("  WARNING: scoring rules differ, so some flips below come from scoring, not the system.")
    for stage in [s for s in sa["stages"] if s in sb["stages"]]:
        def majority(results):
            votes: dict[str, list[bool]] = {}
            for r in results:
                if r["stage"] == stage:
                    votes.setdefault(r["case_id"], []).append(r["passed"])
            return {k: sum(v) / len(v) >= 0.5 for k, v in votes.items()}
        pa, pb = majority(ra), majority(rb)
        common = sorted(set(pa) & set(pb))   # only cases scored in both runs are comparable
        na, nb = sum(pa[k] for k in common), sum(pb[k] for k in common)
        delta = 100 * (nb - na) / len(common) if common else 0.0
        out += ["", f"[{stage}] on {len(common)} common case(s): {na} -> {nb} passed  ({delta:+.0f} points)"]
        if len(common) < max(len(pa), len(pb)):
            out.append(f"    (A scored {len(pa)} case(s), B scored {len(pb)}; the rest are not compared)")
        broke = sorted(k for k in common if pa[k] and not pb[k])
        fixed = sorted(k for k in common if not pa[k] and pb[k])
        if broke:
            out.append(f"    REGRESSIONS (pass -> fail): {', '.join(broke)}")
        if fixed:
            out.append(f"    fixed (fail -> pass):       {', '.join(fixed)}")
    return "\n".join(out)


def list_runs() -> str:
    if not RUNS_DIR.exists():
        return "No runs yet."
    rows = []
    for d in sorted(RUNS_DIR.iterdir()):
        if not (d / "summary.json").exists():
            rows.append(f"{d.name:55} (incomplete)")
            continue
        s = json.loads((d / "summary.json").read_text(encoding="utf-8"))
        rates = "  ".join(f"{k} {100 * v['overall']['rate']:.0f}%" for k, v in s["stages"].items())
        rows.append(f"{d.name:55} {rates}")
    return "\n".join(rows)
