"""Company AI gateway client (OpenAI-compatible chat/completions and embeddings over HTTPS).

Selected with KM_LLM_PROVIDER=gateway (chat) and KM_EMBEDDING_MODEL=gateway:<model> (embeddings).
Mirrors the gateway's sample script: the corporate certificate store via truststore, a Bearer
token (staff AM token or service-account JWT) and the x-correlation-id / x-usersession-id headers.
"""
import json
import logging
import re
import ssl
import time
import uuid

import httpx
from pydantic import ValidationError

from km.config import Settings
from km.llm.base import LLMError, T
from km.observability import generation

log = logging.getLogger(__name__)

_RETRY_STATUS = {429, 500, 502, 503, 504}


def model_label(url: str | None, explicit: str | None = None) -> str:
    """A readable model name for traces and benchmark configs: KM_GATEWAY_MODEL, else the URL
    segment before /chat/completions or /embeddings (…/<provider>/<model>/chat/completions)."""
    if explicit:
        return explicit
    m = re.search(r"/([^/]+)/(?:chat/completions|embeddings)/?$", url or "")
    return m.group(1) if m else "gateway"


class GatewayTransport:
    """Authenticated HTTPS POST to the gateway, with retries and readable errors."""

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        token = settings.gateway_token.get_secret_value() if settings.gateway_token else ""
        if not token:
            raise LLMError("KM_GATEWAY_TOKEN is not set in .env")
        self._token = token
        self._auth = settings.gateway_auth
        self._session_id = str(uuid.uuid4())  # one user session per process
        self._retries = settings.gateway_max_retries
        verify: ssl.SSLContext | bool = True
        if settings.gateway_use_truststore:
            import truststore  # the OS certificate store, which holds the corporate root CA
            verify = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self._client = httpx.Client(timeout=settings.gateway_timeout_s, verify=verify,
                                    transport=transport)  # HTTPS_PROXY is honoured

    def _headers(self) -> dict:
        h = {"Authorization": f"Bearer {self._token}",
             "Content-Type": "application/json",
             "x-correlation-id": str(uuid.uuid4()),
             "x-usersession-id": self._session_id}
        if self._auth == "staff":
            h["Token_Type"] = "SESSION_TOKEN"
        return h

    def post(self, url: str, body: dict) -> dict:
        for attempt in range(self._retries + 1):
            last = attempt == self._retries
            try:
                resp = self._client.post(url, headers=self._headers(), json=body)
            except httpx.TransportError as e:
                if last:
                    raise LLMError(f"Cannot reach the AI gateway at {httpx.URL(url).host} "
                                   f"({type(e).__name__}): check VPN / office network, the URL, "
                                   "HTTPS_PROXY and certificates; `python testCompanyApi.py` "
                                   "runs a step-by-step network check") from e
                time.sleep(2 ** attempt)
                continue
            if resp.status_code in _RETRY_STATUS and not last:
                log.warning("AI gateway HTTP %s; retrying", resp.status_code)
                time.sleep(2 ** attempt)
                continue
            if resp.status_code in (401, 403):
                raise LLMError(f"AI gateway rejected the token (HTTP {resp.status_code}): refresh "
                               "KM_GATEWAY_TOKEN and check KM_GATEWAY_AUTH. " + resp.text[:300])
            if resp.status_code != 200:
                raise LLMError(f"AI gateway returned HTTP {resp.status_code}: {resp.text[:500]}")
            try:
                return resp.json()
            except ValueError as e:
                raise LLMError(f"AI gateway returned non-JSON: {resp.text[:300]}") from e
        raise AssertionError("unreachable")


def _strip_to_json(text: str) -> str:
    """Models sometimes wrap JSON in ``` fences or add a sentence; keep the outermost object."""
    text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip())
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if start >= 0 and end > start else text


class GatewayClient:
    """LLMClient over the gateway's OpenAI-style chat/completions endpoint."""

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        if not settings.gateway_chat_url:
            raise LLMError("KM_GATEWAY_CHAT_URL is not set in .env")
        self._http = GatewayTransport(settings, transport)
        self._url = settings.gateway_chat_url
        self._model = settings.gateway_model          # sent in the body only when set
        self._label = model_label(self._url, self._model)
        self._json_mode = settings.gateway_json_mode
        self._max_tokens = settings.gateway_max_tokens

    # ---- LLMClient interface ----
    def complete(self, system: str, user: str) -> str:
        with generation("llm.complete", self._label, {"system": system, "user": user}) as gen:
            text, resp = self._chat([{"role": "system", "content": system},
                                     {"role": "user", "content": user}])
            gen.update(output=text, usage_details=self._usage(resp),
                       metadata={"finish_reason": self._finish(resp)})
        return text

    def structured(self, system: str, user: str, schema: type[T]) -> T:
        json_schema = schema.model_json_schema()
        sys_prompt = (f"{system}\n\nReply with ONLY one JSON object, no prose and no code fences, "
                      f"that matches this JSON Schema:\n{json.dumps(json_schema)}")
        extra = {}
        if self._json_mode == "json_object":
            extra["response_format"] = {"type": "json_object"}
        elif self._json_mode == "json_schema":
            extra["response_format"] = {"type": "json_schema", "json_schema": {
                "name": schema.__name__, "schema": json_schema, "strict": False}}
        messages = [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user}]
        name = f"llm.structured.{schema.__name__}"
        with generation(name, self._label, {"system": sys_prompt, "user": user}) as gen:
            text, resp = self._chat(messages, **extra)
            try:
                parsed = schema.model_validate_json(_strip_to_json(text))
            except ValidationError as e:  # one repair round: show the model its error
                log.warning("Gateway output did not match %s; asking for a fix", schema.__name__)
                messages += [{"role": "assistant", "content": text},
                             {"role": "user", "content": f"That reply was not valid: {e}. "
                              "Reply with only the corrected JSON object."}]
                text, resp = self._chat(messages, **extra)
                try:
                    parsed = schema.model_validate_json(_strip_to_json(text))
                except ValidationError as e2:
                    raise LLMError(f"Gateway output does not match {schema.__name__}: {e2}") from e2
            gen.update(output=parsed.model_dump(), usage_details=self._usage(resp),
                       metadata={"finish_reason": self._finish(resp)})
        return parsed

    # ---- internals ----
    def _chat(self, messages: list[dict], **extra) -> tuple[str, dict]:
        body: dict = {"messages": messages, **extra}
        if self._model:
            body["model"] = self._model
        if self._max_tokens:
            body["max_tokens"] = self._max_tokens
        resp = self._http.post(self._url, body)
        try:
            choice = resp["choices"][0]
            content = choice["message"].get("content") or ""
        except (KeyError, IndexError, TypeError, AttributeError) as e:
            raise LLMError(f"Unexpected gateway response: {json.dumps(resp)[:300]}") from e
        if isinstance(content, list):  # some providers return content parts
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        if choice.get("finish_reason") == "content_filter":
            raise LLMError("The gateway's content filter blocked this request")
        if choice.get("finish_reason") == "length":
            log.warning("Gateway reply was cut off (finish_reason=length); raise KM_GATEWAY_MAX_TOKENS")
        return content, resp

    @staticmethod
    def _finish(resp: dict) -> str | None:
        return (resp.get("choices") or [{}])[0].get("finish_reason")

    @staticmethod
    def _usage(resp: dict) -> dict:
        u = resp.get("usage") or {}
        return {"input_tokens": u.get("prompt_tokens", 0), "output_tokens": u.get("completion_tokens", 0)}


class GatewayEmbedder:
    """Text embeddings from the gateway's OpenAI-style /embeddings endpoint."""

    def __init__(self, settings: Settings, model: str, transport: httpx.BaseTransport | None = None):
        if not settings.gateway_embed_url:
            raise LLMError("KM_EMBEDDING_MODEL uses the gateway but KM_GATEWAY_EMBED_URL is not set")
        self._http = GatewayTransport(settings, transport)
        self._url = settings.gateway_embed_url
        self._model = model
        self._batch = max(1, settings.gateway_embed_batch)

    def __call__(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), self._batch):
            batch = texts[i:i + self._batch]
            body = {"input": batch}
            if self._model:
                body["model"] = self._model
            vectors += self._parse(self._http.post(self._url, body), len(batch))
        return vectors

    @staticmethod
    def _parse(resp: dict, expected: int) -> list[list[float]]:
        if isinstance(resp.get("data"), list):  # OpenAI format
            rows = sorted(resp["data"], key=lambda r: r.get("index", 0))
            vectors = [r["embedding"] for r in rows]
        elif isinstance(resp.get("embeddings"), list):  # {"embeddings": [[...]] or [{"values": [...]}]}
            vectors = [e["values"] if isinstance(e, dict) else e for e in resp["embeddings"]]
        else:
            raise LLMError(f"Unexpected embeddings response: {json.dumps(resp)[:300]}")
        if len(vectors) != expected:
            raise LLMError(f"Gateway returned {len(vectors)} embeddings for {expected} texts")
        return vectors
