import re
from dataclasses import dataclass, field

from km.domain.models import DocChunk, SqlResult
from km.storage.vector_store import VectorStore

_YEAR = re.compile(r"\b(20\d{2})\b")
_DATE = re.compile(r"^(20\d{2})-\d{2}-\d{2}")
_REGION_COLUMNS = ("office", "region", "location", "country")


@dataclass
class RetrievalHints:
    """Facts that decide WHICH document applies: the region of the person, the year of the event."""
    regions: set[str] = field(default_factory=set)
    years: set[int] = field(default_factory=set)

    def __bool__(self) -> bool:
        return bool(self.regions or self.years)


def hints_from(question: str, sql: SqlResult | None) -> RetrievalHints:
    """Years named in the question, plus offices and event years found in the SQL rows."""
    hints = RetrievalHints(years={int(y) for y in _YEAR.findall(question)})
    for row in (sql.rows if sql else []):
        for col, value in row.items():
            if not isinstance(value, str):
                continue
            if any(c in col.lower() for c in _REGION_COLUMNS):
                hints.regions.add(value)
            elif "hire" not in col.lower() and (m := _DATE.match(value)):
                hints.years.add(int(m.group(1)))   # an event date: which policy version applied
    return hints


class DocRetriever:
    def __init__(self, store: VectorStore, top_k: int, extra_k: int = 2):
        self._store, self._k, self._extra = store, top_k, extra_k

    def retrieve(self, question: str, hints: RetrievalHints | None = None) -> list[DocChunk]:
        chunks = self._store.search(question, self._k)
        if hints:
            for region in sorted(hints.regions):     # regional addenda for the person's office
                chunks += self._store.search(question, self._extra, where={"region": region})
            for year in sorted(hints.years):         # the policy version in force that year
                where = {"$and": [{"effective_from": {"$lte": year * 10000 + 1231}},
                                  {"effective_to": {"$gte": year * 10000 + 101}}]}
                chunks += self._store.search(question, self._extra, where=where)
        seen, unique = set(), []
        for c in chunks:
            key = (c.source, c.location, c.text[:80])
            if key not in seen:
                seen.add(key)
                unique.append(c)
        return unique
