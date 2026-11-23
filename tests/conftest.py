import pytest

from km.domain.models import Claim, Route, Verdict


class FakeLLM:
    """Returns canned objects instead of calling a real LLM."""

    def __init__(self, route="structured", supported=True,
                 sql="SELECT COUNT(*) AS n FROM employees", answer="There are 4 employees [SQL]."):
        self.route, self.supported, self.sql, self.answer = route, supported, sql, answer

    def complete(self, system, user):
        return self.answer

    def structured(self, system, user, schema):
        if schema is Route:
            return Route(intent=self.route, reason="test")
        if schema is Verdict:
            claim = Claim(claim=self.answer, supported=self.supported, evidence_tag="SQL")
            return Verdict(claims=[claim], verdict="grounded")
        return schema(sql=self.sql)  # the SQL writer's output model


@pytest.fixture
def make_llm():
    return FakeLLM
