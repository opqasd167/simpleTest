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
    meta: dict = {}  # document metadata: status, region, effective_from/to (YYYYMMDD ints), language

    def label(self) -> str:
        """'file, page 2; status superseded; applies 2025-01-01 to 2025-12-31; region Singapore'"""
        parts = [f"{self.source}, {self.location}"]
        if self.meta.get("status"):
            parts.append(f"status {self.meta['status']}")
        lo, hi = self.meta.get("effective_from"), self.meta.get("effective_to")
        if lo:
            end = "no end date" if not hi or hi >= 99990000 else _ymd(hi)
            parts.append(f"applies {_ymd(lo)} to {end}")
        if self.meta.get("region"):
            parts.append(f"region {self.meta['region']}")
        return "; ".join(parts)


def _ymd(n: int) -> str:
    s = str(n)
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"


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
        parts = [f"[D{i + 1}] ({d.label()})\n{d.text}" for i, d in enumerate(self.docs)]
        if self.sql:
            parts.append(f"[SQL] query: {self.sql.sql}\nrows: {json.dumps(self.sql.rows, default=str)}")
        return "\n\n".join(parts)

    def items(self) -> list["EvidenceItem"]:
        """The same evidence as render(), one item per tag, so a UI can show what [D2] refers to."""
        items = [EvidenceItem(tag=f"D{i + 1}", label=d.label(), text=d.text) for i, d in enumerate(self.docs)]
        if self.sql:
            items.append(EvidenceItem(tag="SQL", label=self.sql.sql,
                                      text=json.dumps(self.sql.rows, default=str, ensure_ascii=False)))
        return items


class EvidenceItem(BaseModel):
    tag: str    # "D1".."Dn" or "SQL", as cited in the answer
    label: str  # document label, or the SQL query
    text: str   # chunk text, or the SQL rows as JSON


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
    evidence: list[EvidenceItem] = []
    latency_ms: int = 0
