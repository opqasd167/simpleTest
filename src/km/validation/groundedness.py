from datetime import date

from km.domain.models import Evidence, Verdict
from km.llm import prompts
from km.llm.base import LLMClient


class GroundednessValidator:
    def __init__(self, llm: LLMClient):
        self._llm = llm

    def check(self, answer: str, evidence: Evidence) -> Verdict:
        verdict = self._llm.structured(
            prompts.VALIDATOR.format(today=date.today().isoformat()),
            f"Evidence:\n{evidence.render()}\n\nAnswer to check:\n{answer}",
            Verdict)
        return self._relabel(verdict)

    @staticmethod
    def _relabel(v: Verdict) -> Verdict:
        """Recompute the label from the claims, so the verdict cannot contradict its own claims."""
        supported = sum(c.supported for c in v.claims)
        if not v.claims or supported == 0:
            label = "not_grounded"
        elif supported == len(v.claims):
            label = "grounded"
        else:
            label = "partially_grounded"
        return v.model_copy(update={"verdict": label})
