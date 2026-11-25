"""Smoke test for the company AI gateway, using the same .env settings as the app.

    python testCompanyApi.py                    # chat (and embeddings, if configured)
    python testCompanyApi.py "your question"

Needs in .env: KM_GATEWAY_CHAT_URL, KM_GATEWAY_TOKEN, KM_GATEWAY_AUTH (staff | service);
optional: KM_GATEWAY_EMBED_URL and KM_EMBEDDING_MODEL=gateway:<model>.
The request matches the gateway 2.0 sample script: Bearer token, Token_Type (staff only),
x-correlation-id / x-usersession-id, TLS via the OS certificate store (truststore).
"""
import sys

from km.config import Settings
from km.llm.base import LLMError
from km.llm.gateway_client import GatewayClient, GatewayEmbedder

GATEWAY_EMBEDDING_PREFIX = "gateway:"


def main() -> int:
    s = Settings()
    question = sys.argv[1] if len(sys.argv) > 1 else "hi, how are you?"
    ok = True

    print(f"Chat URL: {s.gateway_chat_url}\nAuth:     {s.gateway_auth}")
    try:
        print("Response:", GatewayClient(s).complete("You are a helpful assistant.", question))
    except LLMError as e:
        print("Chat FAILED:", e)
        ok = False

    if s.gateway_embed_url:
        model = s.embedding_model.removeprefix(GATEWAY_EMBEDDING_PREFIX) \
            if s.embedding_model.startswith(GATEWAY_EMBEDDING_PREFIX) else ""
        print(f"\nEmbed URL: {s.gateway_embed_url}")
        try:
            vectors = GatewayEmbedder(s, model)(["annual leave policy", "expense limits"])
            print(f"Embeddings OK: {len(vectors)} vectors of dimension {len(vectors[0])}")
        except LLMError as e:
            print("Embeddings FAILED:", e)
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
