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
