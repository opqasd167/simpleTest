from fastapi.testclient import TestClient

from km.api.app import app, get_service
from km.domain.models import AskResult


class StubService:
    def ask(self, question):
        return AskResult(question=question, status="grounded", answer="stub [SQL]")


def test_health():
    assert TestClient(app).get("/health").json() == {"status": "ok"}


def test_ask_returns_result():
    app.dependency_overrides[get_service] = lambda: StubService()
    try:
        r = TestClient(app).post("/ask", json={"question": "How many engineers?"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["status"] == "grounded"


def test_ask_rejects_empty_question():
    r = TestClient(app).post("/ask", json={"question": ""})
    assert r.status_code == 422


def test_questions_and_feedback_are_logged(tmp_path, monkeypatch):
    import json

    import km.api.app as api
    from km.config import Settings

    log = tmp_path / "questions.jsonl"
    monkeypatch.setattr(api, "get_settings", lambda: Settings(question_log=log))
    app.dependency_overrides[get_service] = lambda: StubService()
    try:
        client = TestClient(app)
        client.post("/ask", json={"question": "How many engineers?"})
        r = client.post("/feedback", json={"question": "How many engineers?", "helpful": False, "comment": "wrong"})
    finally:
        app.dependency_overrides.clear()
    assert r.json() == {"status": "recorded"}
    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [r["type"] for r in records] == ["question", "feedback"]
    assert records[0]["status"] == "grounded" and records[1]["helpful"] is False


def test_home_redirects_to_ui_or_docs():
    import km.api.app as api

    r = TestClient(app).get("/", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == ("/ui" if api.HAS_UI else "/docs")


def test_chat_ui_is_served_when_installed():
    import pytest

    pytest.importorskip("gradio")
    r = TestClient(app).get("/ui/")
    assert r.status_code == 200 and "KM Assistant" in r.text


def test_ui_details_show_evidence_and_claims():
    import pytest

    pytest.importorskip("gradio")
    from km.api.ui import _answer_md, _details_md
    from km.domain.models import Claim, DocChunk, Evidence, Route, SqlResult, Verdict

    ev = Evidence(docs=[DocChunk(source="Leave.pdf", location="page 2", text="20 days")],
                  sql=SqlResult(sql="SELECT 1 AS n", rows=[{"n": 1}]))
    result = AskResult(question="q?", status="grounded", answer="20 days [D1], n=1 [SQL]",
                       route=Route(intent="hybrid", reason="needs both"), evidence=ev.items(),
                       verdict=Verdict(claims=[Claim(claim="20 days", supported=True, evidence_tag="D1")],
                                       verdict="grounded"))
    assert [e.tag for e in result.evidence] == ["D1", "SQL"]
    assert "**[D1]**" in _answer_md(result)
    details = _details_md(result)
    assert "Leave.pdf, page 2" in details and "SELECT 1 AS n" in details and "| n |" in details
    assert "`hybrid`" in details and "✅" in details
