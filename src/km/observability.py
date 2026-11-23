"""Langfuse tracing. On only when LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set.

The rest of the code uses span(), generation(), score_trace(), trace_attributes() and flush()
from here and never imports langfuse directly. With tracing off, every call is a no-op.
"""
import os
from contextlib import contextmanager

from dotenv import load_dotenv

load_dotenv()  # Settings does not copy .env into os.environ, but the Langfuse SDK reads from there
ENABLED = bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))
# false = send timings, token counts and scores, but no prompts, answers or document text
CAPTURE_CONTENT = os.getenv("KM_TRACE_CONTENT", "true").lower() == "true"

if ENABLED:
    from langfuse import get_client, propagate_attributes


class _Observation:
    """Wraps a Langfuse observation; does nothing when tracing is off."""

    def __init__(self, inner=None):
        self._inner = inner

    def update(self, **fields):
        if self._inner is None:
            return
        if not CAPTURE_CONTENT:
            fields.pop("input", None)
            fields.pop("output", None)
        if fields:
            self._inner.update(**fields)


@contextmanager
def _observe(as_type: str, name: str, input_: dict | None, **kwargs):
    if not ENABLED:
        yield _Observation()
        return
    with get_client().start_as_current_observation(as_type=as_type, name=name, **kwargs) as obs:
        wrapped = _Observation(obs)
        if input_:
            wrapped.update(input=input_)
        yield wrapped


def span(name: str, **input_):
    """One pipeline step: route, retrieve, write_answer, validate."""
    return _observe("span", name, input_)


def generation(name: str, model: str, input_: dict):
    """One LLM call. Record output and token usage with .update()."""
    return _observe("generation", name, input_, model=model)


def score_trace(name: str, value, data_type: str) -> None:
    if ENABLED:
        get_client().score_current_trace(name=name, value=value, data_type=data_type)


@contextmanager
def trace_attributes(**attrs):
    """Tags, session_id or user_id for every trace started inside this block."""
    if ENABLED:
        with propagate_attributes(**attrs):
            yield
    else:
        yield


def flush() -> None:
    """Send queued traces now. Call it at the end of short scripts."""
    if ENABLED:
        get_client().flush()
