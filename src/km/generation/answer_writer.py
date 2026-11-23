from datetime import date

from km.domain.models import Evidence
from km.llm import prompts
from km.llm.base import LLMClient

INSUFFICIENT = "INSUFFICIENT_EVIDENCE"


class AnswerWriter:
    def __init__(self, llm: LLMClient):
        self._llm = llm

    def write(self, question: str, evidence: Evidence) -> str | None:
        """The answer text, or None when the model says the evidence is not enough."""
        text = self._llm.complete(
            prompts.ANSWER.format(today=date.today().isoformat()),
            f"Evidence:\n{evidence.render()}\n\nQuestion: {question}")
        return None if INSUFFICIENT in text else text.strip()
