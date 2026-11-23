from functools import lru_cache
from importlib.util import find_spec

from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse

from km.api.schemas import AskRequest, FeedbackRequest
from km.config import get_settings
from km.container import build_qa_service
from km.domain.models import AskResult
from km.logging_setup import setup_logging
from km.question_log import log_feedback, log_question
from km.services.qa_service import QAService

setup_logging()
app = FastAPI(title="KM Assistant", version="0.1.0")


@lru_cache
def get_service() -> QAService:
    return build_qa_service(get_settings())


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ask", response_model=AskResult)
def ask(req: AskRequest, service: QAService = Depends(get_service)) -> AskResult:
    result = service.ask(req.question)
    log_question(get_settings().question_log, result, channel="api")
    return result


@app.post("/feedback")
def feedback(req: FeedbackRequest) -> dict:
    """Users flag unhelpful answers; `python -m km.bench harvest` turns them into benchmark cases."""
    log_feedback(get_settings().question_log, req.question, req.helpful, req.comment)
    return {"status": "recorded"}


HAS_UI = find_spec("gradio") is not None  # optional `ui` extra


@app.get("/", include_in_schema=False)
def home() -> RedirectResponse:
    return RedirectResponse("/ui" if HAS_UI else "/docs")


if HAS_UI:
    import gradio as gr

    from km.api.ui import build_ui

    # lambdas look the functions up at call time, so tests can monkeypatch them
    app = gr.mount_gradio_app(app, build_ui(lambda: get_service(), lambda: get_settings()),
                              path="/ui", theme=gr.themes.Soft(), footer_links=[])
