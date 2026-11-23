"""Shared data models. Every layer passes these objects, never raw dicts."""
import json
from typing import Literal

from pydantic import BaseModel

Intent = Literal["unstructured", "structured", "hybrid"]


class Route(BaseModel):
    intent: Intent
    reason: str


class DocChunk(BaseModel):
    source: str
    location: str
    text: str


class SqlResult(BaseModel):
    sql: str
    rows: list[dict]


class Evidence(BaseModel):
    docs: list[DocChunk] = []
    sql: SqlResult | None = None

    def is_empty(self) -> bool:
        return not self.docs and self.sql is None

    def render(self) -> str:
        """Evidence text with the [D1]/[SQL] tags the answer must cite."""
        parts = [f"[D{i + 1}] ({d.source}, {d.location})\n{d.text}" for i, d in enumerate(self.docs)]
        if self.sql:
            parts.append(f"[SQL] query: {self.sql.sql}\nrows: {json.dumps(self.sql.rows, default=str)}")
        return "\n\n".join(parts)


class Claim(BaseModel):
    claim: str
    supported: bool
    evidence_tag: str  # "D2", "SQL" or "none"


class Verdict(BaseModel):
    claims: list[Claim]
    verdict: Literal["grounded", "partially_grounded", "not_grounded"]


class AskResult(BaseModel):
    question: str
    status: Literal["grounded", "partial", "insufficient_evidence", "error"]
    answer: str
    route: Route | None = None
    sources: list[str] = []
    sql: str | None = None
    verdict: Verdict | None = None
    latency_ms: int = 0
