"""Append-only log of real questions and user feedback (JSON lines).

This is where a realistic benchmark comes from: `python -m km.bench harvest` turns logged failures
and negative feedback into draft benchmark cases for a human to review. Off unless KM_QUESTION_LOG is set.
The log contains real user questions, so store and share it as Internal data.
"""
import json
import threading
from datetime import datetime
from pathlib import Path

from km.domain.models import AskResult

_lock = threading.Lock()


def _append(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock, path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_question(path: Path | None, result: AskResult, channel: str) -> None:
    if path is None:
        return
    _append(path, {"type": "question", "ts": datetime.now().isoformat(timespec="seconds"),
                   "channel": channel, "question": result.question, "status": result.status,
                   "route": result.route.intent if result.route else None, "sources": result.sources,
                   "sql": result.sql, "latency_ms": result.latency_ms, "answer": result.answer[:800]})


def log_feedback(path: Path | None, question: str, helpful: bool, comment: str = "") -> None:
    if path is None:
        return
    _append(path, {"type": "feedback", "ts": datetime.now().isoformat(timespec="seconds"),
                   "question": question, "helpful": helpful, "comment": comment[:1000]})
