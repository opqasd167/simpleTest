"""Smoke test for the company AI gateway, using the same .env settings as the app.

    python testCompanyApi.py                    # network check, then chat (and embeddings, if configured)
    python testCompanyApi.py "your question"

Needs in .env: KM_GATEWAY_BASE_URL + KM_GATEWAY_MODEL (or KM_GATEWAY_CHAT_URL), KM_GATEWAY_TOKEN,
KM_GATEWAY_AUTH (staff | service); for embeddings KM_EMBEDDING_MODEL=gateway:<model>.
The request matches the gateway 2.0 sample script: Bearer token, Token_Type (staff only),
x-correlation-id / x-usersession-id, TLS via the OS certificate store (truststore).
"""
import socket
import sys
import urllib.request
from urllib.parse import urlparse

from km.config import ConfigError, Settings
from km.container import GATEWAY_EMBEDDING_PREFIX, check_embedding_config
from km.llm.base import LLMError
from km.llm.gateway_client import GatewayClient, GatewayEmbedder


def tcp_ok(host: str, port: int, timeout: float = 5.0) -> str | None:
    """None if a TCP connection opens, else the reason it did not."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return None
    except OSError as e:
        return f"{type(e).__name__}: {e}"


def network_check(url: str) -> None:
    """DNS, proxy and TCP checks for one endpoint, so a timeout says where it stops."""
    u = urlparse(url)
    host, port = u.hostname or "", u.port or 443
    print(f"  host:  {host}:{port}")
    proxies = urllib.request.getproxies()  # env vars, plus the Windows registry setting
    proxy = proxies.get("https") or proxies.get("all")
    bypass = urllib.request.proxy_bypass(host) if proxy else False
    print(f"  proxy: {proxy or 'none'}" + (" (bypassed for this host)" if bypass else ""))
    try:
        ips = sorted({ai[4][0] for ai in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})
        print(f"  DNS:   OK -> {', '.join(ips)}")
    except OSError as e:
        print(f"  DNS:   FAILED ({e}) -> not on the company network/VPN, or the host name is wrong")
        return
    err = tcp_ok(host, port)
    print(f"  TCP:   {'OK' if err is None else 'FAILED (' + err + ')'}")
    if err and proxy and not bypass:
        p = urlparse(proxy)
        perr = tcp_ok(p.hostname or "", p.port or 80)
        print(f"  proxy TCP: {'OK' if perr is None else 'FAILED (' + perr + ')'}")
    elif err:
        print("  -> direct connection blocked. If the browser reaches the gateway, it probably uses a\n"
              "     proxy: set HTTPS_PROXY in .env (ask IT, or check the browser's proxy settings).")


def main() -> int:
    s = Settings()
    question = sys.argv[1] if len(sys.argv) > 1 else "hi, how are you?"
    ok = True

    print("Settings read from .env:")
    print(f"  KM_LLM_PROVIDER     = {s.llm_provider}" + ("" if s.llm_provider == "gateway" else
          "   <- set to gateway to answer questions through the company gateway"))
    print(f"  KM_GATEWAY_BASE_URL = {s.gateway_base_url or '(not set)'}")
    print(f"  KM_GATEWAY_MODEL    = {s.gateway_model or '(not set)'}")
    token_set = bool(s.gateway_token and s.gateway_token.get_secret_value())
    print(f"  KM_GATEWAY_TOKEN    = {'set' if token_set else '(not set)'}")
    print(f"  KM_EMBEDDING_MODEL  = {s.embedding_model}")
    try:
        check_embedding_config(s)
    except ConfigError as e:
        print(f"\nCONFIG PROBLEM: {e}")
        ok = False
    print()

    if not s.gateway_chat_url:
        print("Set KM_GATEWAY_BASE_URL (or KM_GATEWAY_CHAT_URL) in .env")
        return 1
    print(f"Chat URL: {s.gateway_chat_url}\nModel:    {s.gateway_model or '(from URL)'}\n"
          f"Auth:     {s.gateway_auth}")
    network_check(s.gateway_chat_url)
    try:
        print("Response:", GatewayClient(s).complete("You are a helpful assistant.", question))
    except LLMError as e:
        print("Chat FAILED:", e)
        ok = False

    if s.gateway_embed_url and s.embedding_model.startswith(GATEWAY_EMBEDDING_PREFIX):
        model = s.embedding_model.removeprefix(GATEWAY_EMBEDDING_PREFIX)
        print(f"\nEmbed URL: {s.gateway_embed_url}\nModel:     {model}")
        if urlparse(s.gateway_embed_url).hostname != urlparse(s.gateway_chat_url).hostname:
            network_check(s.gateway_embed_url)
        try:
            vectors = GatewayEmbedder(s, model)(["annual leave policy", "expense limits"])
            print(f"Embeddings OK: {len(vectors)} vectors of dimension {len(vectors[0])}")
        except LLMError as e:
            print("Embeddings FAILED:", e)
            ok = False

    if not s.embedding_model.startswith(GATEWAY_EMBEDDING_PREFIX):
        print(f"\nNote: KM_EMBEDDING_MODEL={s.embedding_model} is a LOCAL model. `km ingest` downloads it "
              "on first use\n(Hugging Face / Chroma S3), which company networks often block.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
