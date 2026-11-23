"""Wraps any LLMClient and counts calls, prompt size and time. Used by the scale eval
to turn a small measured run into a cost and time projection."""
import threading
import time

from km.llm.base import LLMClient, T


class MeteredLLM:
    def __init__(self, inner: LLMClient):
        self.inner = inner
        self._lock = threading.Lock()
        self.calls = 0
        self.in_chars = 0
        self.out_chars = 0
        self.seconds = 0.0

    def complete(self, system: str, user: str) -> str:
        start = time.perf_counter()
        out = self.inner.complete(system, user)
        self._record(system + user, out, start)
        return out

    def structured(self, system: str, user: str, schema: type[T]) -> T:
        start = time.perf_counter()
        out = self.inner.structured(system, user, schema)
        self._record(system + user, out.model_dump_json(), start)
        return out

    def _record(self, prompt: str, output: str, start: float) -> None:
        with self._lock:
            self.calls += 1
            self.in_chars += len(prompt)
            self.out_chars += len(output)
            self.seconds += time.perf_counter() - start
