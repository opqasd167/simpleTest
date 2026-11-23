"""Turn the question log into DRAFT benchmark cases for human review.

Real questions are the best benchmark: they use real wording and hit real gaps. A draft is selected
when the system refused or only partly answered, failed, or a user marked the answer unhelpful
(or every question, with --all). Duplicates of existing cases are skipped. Each draft is tagged
needs_review; a person must fill in the expected result before moving it into dataset.jsonl.
"""
import json
from pathlib import Path

from km.bench.dataset import load_cases
from km.bench.metrics import normalize

SUSPECT_STATUSES = {"insufficient_evidence", "partial", "error"}


def harvest(log: Path, dataset: Path, out: Path, include_all: bool = False) -> int:
    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    unhelpful = {normalize(r["question"]): r.get("comment", "") for r in records
                 if r.get("type") == "feedback" and not r.get("helpful")}
    known = {normalize(c.question) for c in load_cases(dataset)} if dataset.exists() else set()
    if out.exists():
        known |= {normalize(json.loads(line)["question"])
                  for line in out.read_text(encoding="utf-8").splitlines() if line.strip()}

    drafts = []
    for r in records:
        if r.get("type") != "question":
            continue
        key = normalize(r["question"])
        if key in known:
            continue
        reason = ("user marked unhelpful: " + unhelpful[key]) if key in unhelpful else (
            f"status {r['status']}" if r["status"] in SUSPECT_STATUSES else "")
        if not reason and not include_all:
            continue
        known.add(key)
        drafts.append({
            "id": f"LOG{len(known):04d}", "category": "from_log", "question": r["question"],
            "expected_route": r.get("route"), "expected_status": "grounded",
            "must_include": [], "must_not_include": [], "reference_answer": "",
            "tags": ["needs_review"], "difficulty": 2,
            "review_notes": {"why_selected": reason or "--all", "observed_status": r["status"],
                             "observed_answer": r.get("answer", "")[:400], "observed_sql": r.get("sql"),
                             "observed_sources": r.get("sources"), "asked_at": r.get("ts")},
        })
    with out.open("a", encoding="utf-8") as f:
        for d in drafts:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    return len(drafts)
