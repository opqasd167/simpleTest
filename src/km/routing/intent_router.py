from km.domain.models import Route
from km.llm import prompts
from km.llm.base import LLMClient


class IntentRouter:
    def __init__(self, llm: LLMClient):
        self._llm = llm

    def route(self, question: str, schema: str) -> Route:
        return self._llm.structured(prompts.ROUTER.format(schema=schema), question, Route)
