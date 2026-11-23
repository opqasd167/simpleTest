"""Benchmark case format (one JSON object per line in <corpus>/dataset.jsonl)."""
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel


class GoldSource(BaseModel):
    source: str                   # file name, e.g. "Leave_Policy_2026.pdf"
    location: str | None = None   # "page 2" for PDFs; None = anywhere in the file


class Case(BaseModel):
    id: str
    category: str                 # e.g. doc_lookup, sql_aggregate, hybrid, adversarial, known_gap
    question: str
    expected_route: Literal["unstructured", "structured", "hybrid"] | None = None  # None = any route
    acceptable_routes: list[str] = []     # other routes that are also correct for this question
    expected_status: Literal["grounded", "insufficient_evidence"] = "grounded"
    gold_sources: list[GoldSource] = []   # retrieval stage
    gold_sql: str | None = None           # sql stage: its result is the ground truth
    must_include: list[str] = []          # e2e: facts the answer must contain
    must_not_include: list[str] = []      # e2e: things the answer must never say
    reference_answer: str = ""            # e2e with --judge
    tags: list[str] = []
    difficulty: int = 1                   # 1 easy .. 3 hard


def load_cases(path: Path) -> list[Case]:
    return [Case.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def select(cases: list[Case], ids: str | None = None, categories: str | None = None,
           tags: str | None = None) -> list[Case]:
    out = cases
    if ids:
        wanted = set(ids.split(","))
        out = [c for c in out if c.id in wanted]
    if categories:
        wanted = set(categories.split(","))
        out = [c for c in out if c.category in wanted]
    if tags:
        wanted = set(tags.split(","))
        out = [c for c in out if wanted & set(c.tags)]
    return out


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)
