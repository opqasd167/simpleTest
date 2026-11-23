from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """The LLM call failed, was refused, or the backend is unreachable."""


class LLMClient(Protocol):
    def complete(self, system: str, user: str) -> str: ...

    def structured(self, system: str, user: str, schema: type[T]) -> T: ...
