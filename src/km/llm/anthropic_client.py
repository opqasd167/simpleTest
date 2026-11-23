"""Production LLM client: the only file that imports the anthropic SDK and knows the gateway."""
from contextlib import contextmanager

import anthropic

from km.config import Settings
from km.llm.base import LLMError, T
from km.observability import generation  # Langfuse; a no-op when tracing is off


@contextmanager
def _gateway_errors():
    try:
        yield
    except anthropic.AuthenticationError as e:
        raise LLMError("Token rejected: check KM_LLM_API_TOKEN and KM_LLM_AUTH_MODE") from e
    except anthropic.RateLimitError as e:
        raise LLMError("Rate limited by the LLM gateway; retry later") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"LLM gateway returned HTTP {e.status_code}") from e
    except anthropic.APIConnectionError as e:
        raise LLMError("Cannot reach the LLM gateway: check URL, proxy and certificate") from e


def _usage(resp) -> dict:
    return {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}


def _text(resp) -> str:
    return "".join(b.text for b in resp.content if b.type == "text")


class AnthropicClient:
    def __init__(self, settings: Settings):
        token = settings.llm_api_token.get_secret_value() if settings.llm_api_token else ""
        if not token:
            raise LLMError("KM_LLM_API_TOKEN is not set in .env")
        auth = {"auth_token": token} if settings.llm_auth_mode == "bearer" else {"api_key": token}
        self._client = anthropic.Anthropic(
            base_url=settings.llm_base_url or None,  # None = public Anthropic API
            timeout=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
            **auth,
        )
        self._model = settings.llm_model
        self._fallbacks = settings.llm_server_fallbacks

    def complete(self, system: str, user: str) -> str:
        messages = [{"role": "user", "content": user}]
        with generation("llm.complete", self._model, {"system": system, "user": user}) as gen:
            with _gateway_errors():
                if self._fallbacks:  # on a refusal, the API retries on a fallback model
                    resp = self._client.beta.messages.create(
                        model=self._model, max_tokens=16000, system=system, messages=messages,
                        betas=["server-side-fallback-2026-07-01"], fallbacks="default")
                else:
                    resp = self._client.messages.create(
                        model=self._model, max_tokens=16000, system=system, messages=messages)
            gen.update(output=_text(resp), usage_details=_usage(resp),
                       metadata={"stop_reason": resp.stop_reason})
        if resp.stop_reason == "refusal":
            raise LLMError("The model declined this request")
        return _text(resp)

    def structured(self, system: str, user: str, schema: type[T]) -> T:
        name = f"llm.structured.{schema.__name__}"
        with generation(name, self._model, {"system": system, "user": user}) as gen:
            with _gateway_errors():
                resp = self._client.messages.parse(
                    model=self._model, max_tokens=16000, system=system,
                    messages=[{"role": "user", "content": user}],
                    output_format=schema)
            parsed = resp.parsed_output
            gen.update(output=parsed.model_dump() if parsed else None, usage_details=_usage(resp),
                       metadata={"stop_reason": resp.stop_reason})
        if resp.stop_reason == "refusal" or parsed is None:
            raise LLMError("No valid structured output returned")
        return parsed
