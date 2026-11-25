"""Turns a network failure into one line that says which host failed and what to do.

On a company laptop the usual causes are a blocked download host (embedding models come from
Hugging Face or Chroma's S3 bucket on first use) or the AI gateway being unreachable off VPN.
"""
import httpx

_HINTS = (
    (("huggingface.co", "hf.co"),
     "the local embedding model ({model}) is downloaded from Hugging Face on first use, and this "
     "network blocks it. Use the company gateway instead (KM_EMBEDDING_MODEL=gateway:<model> + "
     "KM_GATEWAY_EMBED_URL), or copy the model cache from a machine that has it (FASTEMBED_CACHE_PATH)."),
    (("chroma-onnx-models",),
     "Chroma's default embedding model is downloaded on first use, and this network blocks it. "
     "Use KM_EMBEDDING_MODEL=gateway:<model> + KM_GATEWAY_EMBED_URL, or copy ~/.cache/chroma from "
     "a machine that has it."),
)


def _find_transport_error(exc: BaseException) -> httpx.TransportError | None:
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, httpx.TransportError):
            return exc
        exc = exc.__cause__ or exc.__context__
    return None


def explain(exc: BaseException, embedding_model: str = "", gateway_hosts: tuple[str, ...] = ()) -> str | None:
    """A one-line diagnosis if `exc` (or its cause) is an httpx network error, else None."""
    err = _find_transport_error(exc)
    if err is None:
        return None
    try:
        host = err.request.url.host
    except RuntimeError:  # raised without a request attached
        host = "unknown host"
    what = f"Network error ({type(err).__name__}) reaching {host}"
    for needles, hint in _HINTS:
        if any(n in host for n in needles):
            return f"{what}: {hint.format(model=embedding_model)}"
    if host in gateway_hosts:
        return (f"{what}: the AI gateway is unreachable. Check VPN / office network, the URL in .env, "
                "and HTTPS_PROXY if your company uses a proxy. `python testCompanyApi.py` runs a "
                "step-by-step network check.")
    return f"{what}: check VPN, proxy (HTTPS_PROXY) and firewall rules for this host."
