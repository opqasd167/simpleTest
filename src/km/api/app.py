from functools import lru_cache

from fastapi import Depends, FastAPI

from km.api.schemas import AskRequest
from km.config import get_settings
from km.container import build_qa_service
from km.domain.models import AskResult
from km.logging_setup import setup_logging
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
    return service.ask(req.question)
