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

from km.config import Settings
from km.llm.base import LLMError
from km.llm.gateway_client import GatewayClient, GatewayEmbedder

GATEWAY_EMBEDDING_PREFIX = "gateway:"


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

    if s.gateway_embed_url:
        model = s.embedding_model.removeprefix(GATEWAY_EMBEDDING_PREFIX) \
            if s.embedding_model.startswith(GATEWAY_EMBEDDING_PREFIX) else ""
        print(f"\nEmbed URL: {s.gateway_embed_url}")
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
