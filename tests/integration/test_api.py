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
