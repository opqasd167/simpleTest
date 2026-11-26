"""Company AI gateway client, tested against a mock HTTP transport (no network)."""
import json

import httpx
import pytest

from km.config import Settings
from km.container import build_judge_llm, build_vector_store
from km.domain.models import DocChunk, Route
from km.llm.base import LLMError
from km.llm.gateway_client import GatewayClient, GatewayEmbedder, model_label

CHAT_URL = "https://gw.example/proxy/use-case-1/openai/gpt-x/chat/completions"
EMBED_URL = "https://gw.example/proxy/use-case-1/openai/embed-x/embeddings"


def settings(**kw) -> Settings:
    base = dict(_env_file=None, llm_provider="gateway", gateway_chat_url=CHAT_URL,
                gateway_embed_url=EMBED_URL, gateway_token="tok-123", gateway_max_retries=0,
                gateway_use_truststore=False)
    return Settings(**{**base, **kw})


def chat_reply(content: str, finish: str = "stop") -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": finish}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}}


class Recorder:
    """httpx transport that records requests and replays canned (status, json) responses."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        status, body = self.responses.pop(0)
        return httpx.Response(status, json=body)

    def body(self, i: int = -1) -> dict:
        return json.loads(self.requests[i].content)

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)


def test_complete_sends_staff_headers_and_messages():
    rec = Recorder((200, chat_reply("hello")))
    client = GatewayClient(settings(), transport=rec.transport)
    assert client.complete("be brief", "hi") == "hello"
    req = rec.requests[0]
    assert str(req.url) == CHAT_URL
    assert req.headers["Authorization"] == "Bearer tok-123"
    assert req.headers["Token_Type"] == "SESSION_TOKEN"
    assert req.headers["x-correlation-id"] and req.headers["x-usersession-id"]
    assert rec.body()["messages"] == [{"role": "system", "content": "be brief"},
                                      {"role": "user", "content": "hi"}]
    assert "model" not in rec.body()  # the URL already names the model


def test_service_auth_has_no_session_token_type():
    rec = Recorder((200, chat_reply("ok")))
    GatewayClient(settings(gateway_auth="service", gateway_model="gpt-x"),
                  transport=rec.transport).complete("s", "u")
    assert "Token_Type" not in rec.requests[0].headers
    assert rec.body()["model"] == "gpt-x"


def test_structured_parses_fenced_json():
    rec = Recorder((200, chat_reply('```json\n{"intent": "structured", "reason": "count"}\n```')))
    route = GatewayClient(settings(), transport=rec.transport).structured("route it", "how many?", Route)
    assert route == Route(intent="structured", reason="count")
    assert "JSON Schema" in rec.body()["messages"][0]["content"]
    assert "response_format" not in rec.body()


def test_structured_repairs_invalid_json_once():
    rec = Recorder((200, chat_reply('{"intent": "weather"}')),
                   (200, chat_reply('{"intent": "hybrid", "reason": "both"}')))
    route = GatewayClient(settings(), transport=rec.transport).structured("s", "u", Route)
    assert route.intent == "hybrid"
    assert rec.body(1)["messages"][-1]["content"].startswith("That reply was not valid")


def test_structured_json_schema_mode_sends_response_format():
    rec = Recorder((200, chat_reply('{"intent": "unstructured", "reason": "policy"}')))
    GatewayClient(settings(gateway_json_mode="json_schema"), transport=rec.transport).structured("s", "u", Route)
    assert rec.body()["response_format"]["json_schema"]["name"] == "Route"


def test_token_rejected_is_a_clear_error():
    rec = Recorder((401, {"error": "expired"}))
    with pytest.raises(LLMError, match="KM_GATEWAY_TOKEN"):
        GatewayClient(settings(), transport=rec.transport).complete("s", "u")


def test_retries_on_server_error(monkeypatch):
    monkeypatch.setattr("km.llm.gateway_client.time.sleep", lambda s: None)
    rec = Recorder((503, {}), (200, chat_reply("recovered")))
    client = GatewayClient(settings(gateway_max_retries=1), transport=rec.transport)
    assert client.complete("s", "u") == "recovered"
    assert len(rec.requests) == 2


def test_missing_token_or_url():
    with pytest.raises(LLMError, match="KM_GATEWAY_TOKEN"):
        GatewayClient(settings(gateway_token=None))
    with pytest.raises(LLMError, match="KM_GATEWAY_BASE_URL"):
        GatewayClient(settings(gateway_chat_url=None))


@pytest.mark.parametrize("value, message", [
    ("https://gw.example/proxy/v1/UC1", "is a URL"),
    ("gateway:https://gw.example/proxy/v1/UC1", "URL after 'gateway:'"),
    ("gateway:", "no model name"),
    ("gemini-2.5-pro", "is your chat model"),
])
def test_embedding_config_mixups_are_explained(tmp_path, value, message):
    from km.config import ConfigError
    s = settings(chroma_dir=tmp_path, embedding_model=value, gateway_model="gemini-2.5-pro")
    with pytest.raises(ConfigError, match=message):
        build_vector_store(s)


def test_gateway_embeddings_without_base_url(tmp_path):
    from km.config import ConfigError
    s = settings(chroma_dir=tmp_path, embedding_model="gateway:uae", gateway_embed_url=None)
    with pytest.raises(ConfigError, match="KM_GATEWAY_BASE_URL"):
        build_vector_store(s)


def test_embedder_batches_and_orders_by_index():
    def reply(n, offset):
        return {"data": [{"index": i, "embedding": [float(offset + i)]} for i in reversed(range(n))]}
    rec = Recorder((200, reply(2, 0)), (200, reply(1, 2)))
    embed = GatewayEmbedder(settings(gateway_embed_batch=2), "embed-x", transport=rec.transport)
    assert embed(["a", "b", "c"]) == [[0.0], [1.0], [2.0]]
    assert rec.body(0) == {"input": ["a", "b"], "model": "embed-x"}
    assert rec.body(1)["input"] == ["c"]


def test_vector_store_uses_gateway_embeddings(tmp_path, monkeypatch):
    calls = []

    def fake_call(self, texts):
        calls.append(texts)
        return [[1.0, 0.0] if "leave" in t else [0.0, 1.0] for t in texts]

    monkeypatch.setattr(GatewayEmbedder, "__call__", fake_call)
    store = build_vector_store(settings(chroma_dir=tmp_path, embedding_model="gateway:embed-x"))
    store.upsert(["1", "2"], [DocChunk(source="a.pdf", location="p1", text="annual leave days"),
                              DocChunk(source="b.pdf", location="p1", text="expense limits")])
    assert store.search("leave policy", k=1)[0].source == "a.pdf"
    assert calls  # documents and the query went through the gateway embedder


def test_model_label_and_judge_url():
    assert model_label(CHAT_URL) == "gpt-x"
    assert model_label(EMBED_URL) == "embed-x"
    assert model_label(CHAT_URL, "explicit") == "explicit"
    other = "https://gw.example/proxy/use-case-1/google/gemini-y/chat/completions"
    judge = build_judge_llm(settings(judge_model=other))
    assert judge._url == other


def _timeout(url: str) -> Exception:
    """A wrapped ConnectTimeout, as raised from deep inside a download library."""
    try:
        try:
            raise httpx.ConnectTimeout("timed out", request=httpx.Request("GET", url))
        except httpx.ConnectTimeout as e:
            raise RuntimeError("download failed") from e
    except RuntimeError as outer:
        return outer


def test_network_error_names_the_blocked_host():
    from km.net_errors import explain
    hf = explain(_timeout("https://huggingface.co/intfloat/x"), "intfloat/multilingual-e5-large")
    assert "huggingface.co" in hf and "gateway:<model>" in hf
    gw = explain(_timeout(CHAT_URL), "default", gateway_hosts=("gw.example",))
    assert "AI gateway is unreachable" in gw
    assert explain(ValueError("not network")) is None


def test_gateway_connect_timeout_names_host():
    def boom(request):
        raise httpx.ConnectTimeout("timed out", request=request)
    client = GatewayClient(settings(), transport=httpx.MockTransport(boom))
    with pytest.raises(LLMError, match="gw.example"):
        client.complete("s", "u")


def test_base_url_like_the_openai_sdk():
    """Same requests as the gateway's OpenAI-SDK sample: base_url + model name in the body."""
    base = "https://gw.example/ai-gateway-ppd-internal-proxy/v1/UC0000001"
    s = settings(gateway_base_url=base + "/", gateway_chat_url=None, gateway_embed_url=None,
                 gateway_model="gemini-2.5-pro", gateway_auth="service")
    assert s.gateway_chat_url == base + "/chat/completions"
    assert s.gateway_embed_url == base + "/embeddings"
    rec = Recorder((200, chat_reply("hi")), (200, {"data": [{"index": 0, "embedding": [0.1, 0.2]}]}))
    GatewayClient(s, transport=rec.transport).complete("s", "Hello, how are you?")
    GatewayEmbedder(s, "uae", transport=rec.transport)(["text"])
    assert str(rec.requests[0].url) == base + "/chat/completions"
    assert rec.body(0)["model"] == "gemini-2.5-pro"
    assert rec.requests[0].headers["Authorization"] == "Bearer tok-123"
    assert "Token_Type" not in rec.requests[0].headers
    assert str(rec.requests[1].url) == base + "/embeddings"
    assert rec.body(1) == {"input": ["text"], "model": "uae"}


def test_base_url_in_chat_url_setting_is_accepted():
    base = "https://gw.example/ai-gateway-ppd-internal-proxy/v1/UC0000001"
    s = settings(gateway_chat_url=base, gateway_embed_url=None)
    assert s.gateway_chat_url == base + "/chat/completions"
    assert s.gateway_embed_url == base + "/embeddings"
