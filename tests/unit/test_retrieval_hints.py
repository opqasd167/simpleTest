import json

import pytest

from km.domain.models import DocChunk, Evidence, SqlResult
from km.ingestion.indexer import Indexer, load_metadata
from km.retrieval.doc_retriever import DocRetriever, RetrievalHints, hints_from
from km.storage.vector_store import VectorStore


def test_hints_from_question_years_and_sql_facts():
    sql = SqlResult(sql="...", rows=[{"name": "Priya Nair", "office": "Singapore", "hire_date": "2024-02-01",
                                      "expense_date": "2025-06-10", "amount_usd": 70.0}])
    h = hints_from("Did it follow the 2025 policy?", sql)
    assert h.regions == {"Singapore"}
    assert h.years == {2025}            # from the question and expense_date; hire_date is ignored
    assert not hints_from("How long is parental leave?", None)


def test_evidence_label_shows_version_and_region():
    chunk = DocChunk(source="Policy_2025.docx", location="body", text="Meals: $60",
                     meta={"status": "superseded", "effective_from": 20250101, "effective_to": 20251231,
                           "region": "group"})
    rendered = Evidence(docs=[chunk]).render()
    assert "status superseded; applies 2025-01-01 to 2025-12-31; region group" in rendered


def test_metadata_dates_become_integers(tmp_path):
    (tmp_path / "_metadata.json").write_text(json.dumps({
        "a.pdf": {"status": "current", "effective_from": "2026-01-01", "region": "group"}}), encoding="utf-8")
    meta = load_metadata(tmp_path)["a.pdf"]
    assert meta["effective_from"] == 20260101 and meta["effective_to"] == 99991231


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    """A tiny index with a group policy, a regional addendum and two policy versions."""
    path = tmp_path_factory.mktemp("chroma")
    vs = VectorStore(path, "hints_test")
    docs = [
        ("group_leave.pdf", "Annual leave is 20 working days per year for all staff.",
         {"region": "group", "effective_from": 20260101, "effective_to": 99991231}),
        ("sg_addendum.pdf", "Singapore staff: annual leave is 18 working days.",
         {"region": "Singapore", "effective_from": 20260101, "effective_to": 99991231}),
        ("expense_2025.docx", "Travel over $1,000 per trip needs VP approval.",
         {"region": "group", "effective_from": 20250101, "effective_to": 20251231}),
        ("expense_2026.docx", "Travel over $1,500 per trip needs VP approval.",
         {"region": "group", "effective_from": 20260101, "effective_to": 99991231}),
    ] + [(f"filler_{i}.pdf", f"Unrelated benefit number {i}: gym, pension, referral bonus.", {}) for i in range(8)]
    vs.upsert([d[0] for d in docs], [DocChunk(source=s, location="page 1", text=t, meta=m) for s, t, m in docs])
    return vs


def test_region_hint_adds_the_regional_addendum(store):
    r = DocRetriever(store, top_k=1)
    plain = {c.source for c in r.retrieve("How much annual leave does Priya get?")}
    hinted = {c.source for c in r.retrieve("How much annual leave does Priya get?",
                                           RetrievalHints(regions={"Singapore"}))}
    assert "sg_addendum.pdf" in hinted
    assert plain <= hinted


def test_year_hint_adds_the_version_in_force(store):
    r = DocRetriever(store, top_k=1, extra_k=1)
    got = {c.source for c in r.retrieve("What was the VP approval threshold for travel?", RetrievalHints(years={2025}))}
    assert "expense_2025.docx" in got
