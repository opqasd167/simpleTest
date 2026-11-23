import json
from pathlib import Path

import pytest

from km.bench.__main__ import check_thresholds
from km.bench.harvest import harvest
from km.ingestion.loaders import load_file

SCANNED = Path("benchmarks/corpora/v2/docs/Board_Minutes_Q4_2025_scanned.pdf")


def test_scanned_pdf_has_no_text_without_ocr():
    [(_, text)] = load_file(SCANNED)
    assert text.strip() == ""


def test_ocr_reads_the_scanned_pdf():
    pytest.importorskip("rapidocr_onnxruntime")
    [(_, text)] = load_file(SCANNED, ocr=True)
    assert "48.2" in text


def test_harvest_drafts_failures_and_negative_feedback(tmp_path):
    log = tmp_path / "questions.jsonl"
    rows = [
        {"type": "question", "question": "What is the meal limit?", "status": "grounded", "route": "unstructured",
         "answer": "$75 [D1]"},                                                             # fine: skipped
        {"type": "question", "question": "Who approved my trip?", "status": "insufficient_evidence",
         "route": "hybrid", "answer": "I could not find..."},                               # refused: drafted
        {"type": "question", "question": "How many wellness days?", "status": "grounded", "route": "unstructured",
         "answer": "5 days"},
        {"type": "feedback", "question": "How many wellness days?", "helpful": False, "comment": "It is 2"},
        {"type": "question", "question": "How often must passwords be changed?", "status": "error"},  # in dataset
    ]
    log.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text(json.dumps({"id": "D04", "category": "doc_lookup",
                                   "question": "How often must passwords be changed?"}) + "\n", encoding="utf-8")
    out = tmp_path / "candidates.jsonl"
    assert harvest(log, dataset, out) == 2
    drafts = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert {d["question"] for d in drafts} == {"Who approved my trip?", "How many wellness days?"}
    assert all("needs_review" in d["tags"] for d in drafts)
    assert harvest(log, dataset, out) == 0          # running again adds no duplicates


def test_fail_under_thresholds(tmp_path):
    (tmp_path / "summary.json").write_text(json.dumps({"stages": {
        "retrieval": {"overall": {"rate": 0.95}}, "e2e": {"overall": {"rate": 0.80}}}}), encoding="utf-8")
    assert check_thresholds(tmp_path, "retrieval=0.9") == []
    assert check_thresholds(tmp_path, "retrieval=0.9,e2e=0.85") == ["e2e: 0.800 < 0.850"]
    assert check_thresholds(tmp_path, "sql=0.5") == ["sql: stage was not run"]
