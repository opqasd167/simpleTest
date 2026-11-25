"""One-command onboarding: set up everything needed to test the KM Assistant.

    python scripts/onboard.py              # interactive (asks how to reach an LLM)
    python scripts/onboard.py --yes        # no questions; keeps .env as it is
    python scripts/onboard.py --offline    # skip every step that calls an LLM

Steps: virtual env -> install -> .env -> seed SQLite -> index documents -> offline tests ->
free retrieval benchmark -> one live question (only when an LLM is configured) -> optional API start.
Safe to re-run: every step is idempotent and an existing .env is never overwritten.
Uses only the standard library, so it runs with any Python 3.11+ before anything is installed.
"""
import argparse
import getpass
import hashlib
import os
import shutil
import socket
import subprocess
import sys
import time
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
STAMP = VENV / ".onboard-installed"       # fingerprint of the last successful install
ENV_FILE, ENV_EXAMPLE = ROOT / ".env", ROOT / ".env.example"
EXTRAS = "dev,ocr,multilingual,ui"           # same as CI
SMOKE_QUESTION = "How many people work in Engineering?"
WIN = os.name == "nt"

results: list[tuple[str, str, str]] = []  # (step, OK|WARN|FAIL|SKIP, detail)


# ---------- output helpers ----------
def banner(text: str) -> None:
    print(f"\n=== {text} " + "=" * max(0, 66 - len(text)), flush=True)


def record(step: str, status: str, detail: str = "") -> None:
    results.append((step, status, detail))
    print(f"[{status}] {step}" + (f": {detail}" if detail else ""), flush=True)


def ask(prompt: str, default: str, interactive: bool) -> str:
    if not interactive:
        return default
    answer = input(f"{prompt} [{default}]: ").strip()
    return answer or default


# ---------- environment helpers ----------
def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if WIN else "bin/python")


def child_env() -> dict:
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PIP_DISABLE_PIP_VERSION_CHECK="1")
    env.pop("VIRTUAL_ENV", None)
    return env


def run(args: list, step: str, ok_detail: str = "") -> bool:
    print(f"$ {' '.join(str(a) for a in args)}", flush=True)
    start = time.time()
    code = subprocess.call([str(a) for a in args], cwd=ROOT, env=child_env())
    took = f"{time.time() - start:.0f}s"
    if code == 0:
        record(step, "OK", f"{ok_detail} ({took})".strip())
        return True
    record(step, "FAIL", f"exit code {code} ({took})")
    return False


def read_env() -> dict[str, str]:
    values = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def set_env(updates: dict[str, str]) -> None:
    """Change KEY=value lines in .env in place (also un-comments '# KEY=' lines); append missing keys."""
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    pending = dict(updates)
    for i, line in enumerate(lines):
        key = line.lstrip("# ").partition("=")[0].strip()
        if key in pending and "=" in line:
            lines[i] = f"{key}={pending.pop(key)}"
    lines += [f"{k}={v}" for k, v in pending.items()]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def llm_status() -> tuple[bool, str]:
    env = {**read_env(), **{k: v for k, v in os.environ.items() if k.startswith("KM_")}}
    provider = env.get("KM_LLM_PROVIDER", "anthropic") or "anthropic"
    if provider == "grok_cli":
        grok = env.get("KM_GROK_BIN") or "grok"
        if shutil.which(grok):
            return True, f"Grok CLI simulator ({grok})"
        return False, f"KM_LLM_PROVIDER=grok_cli but '{grok}' is not on PATH"
    if provider == "gateway":
        missing = [k for k in ("KM_GATEWAY_CHAT_URL", "KM_GATEWAY_TOKEN") if not env.get(k)]
        if missing:
            return False, f"KM_LLM_PROVIDER=gateway but {' and '.join(missing)} not set in .env"
        return True, f"company AI gateway ({env['KM_GATEWAY_CHAT_URL'].split('/')[2]})"
    if env.get("KM_LLM_API_TOKEN"):
        return True, f"company gateway ({env.get('KM_LLM_BASE_URL') or 'api.anthropic.com'})"
    return False, "no KM_LLM_API_TOKEN in .env"


# ---------- steps ----------
def step_python() -> None:
    banner("1. Python")
    if sys.version_info < (3, 11):
        sys.exit(f"Python 3.11+ is required, this is {sys.version.split()[0]}. "
                 "Install it from https://www.python.org/downloads/ and re-run.")
    record("Python", "OK", f"{sys.version.split()[0]} at {sys.executable}")


def step_venv() -> None:
    banner("2. Virtual environment (.venv)")
    py = venv_python()
    if py.exists():
        probe = subprocess.run([str(py), "-c", "import sys; print(sys.version_info >= (3, 11))"],
                               capture_output=True, text=True)
        if probe.returncode == 0 and probe.stdout.strip() == "True":
            record("Virtual env", "OK", "reusing existing .venv")
            return
        print("Existing .venv is broken or older than Python 3.11; recreating it.")
        shutil.rmtree(VENV)
    venv.EnvBuilder(with_pip=True).create(VENV)
    record("Virtual env", "OK", "created .venv")


def install_fingerprint() -> str:
    return hashlib.sha256((ROOT / "pyproject.toml").read_bytes() + EXTRAS.encode()).hexdigest()


def locked_scripts() -> list[str]:
    """Windows cannot overwrite a running .exe: a `km serve` left open makes pip fail on km.exe."""
    if not WIN:
        return []
    locked = []
    for exe in (VENV / "Scripts").glob("km*.exe"):
        try:
            open(exe, "r+b").close()
        except OSError:
            locked.append(exe.name)
    return locked


def step_install(force: bool) -> bool:
    banner(f"3. Install the project and test tools  (.[{EXTRAS}])")
    py = venv_python()
    importable = subprocess.call([str(py), "-c", "import km, pytest"], cwd=ROOT, env=child_env(),
                                 stderr=subprocess.DEVNULL) == 0
    if not force and importable and STAMP.exists() and STAMP.read_text().strip() == install_fingerprint():
        record("Install dependencies", "OK", "already up to date (pyproject.toml unchanged; --reinstall to force)")
        return True
    if locked := locked_scripts():
        record("Install dependencies", "FAIL", f"{', '.join(locked)} is in use: stop any running "
               "`km serve` / `km ask` (Ctrl+C in its window) and run setup again")
        return False
    subprocess.call([str(py), "-m", "pip", "install", "-q", "--upgrade", "pip"], cwd=ROOT, env=child_env())
    if run([py, "-m", "pip", "install", "-e", f".[{EXTRAS}]"], "Install dependencies"):
        STAMP.write_text(install_fingerprint())
        return True
    return False


def step_env(interactive: bool) -> None:
    banner("4. Configuration (.env)")
    if ENV_FILE.exists():
        print(".env already exists; leaving your settings as they are.")
    else:
        shutil.copyfile(ENV_EXAMPLE, ENV_FILE)
        print("Created .env from .env.example.")

    ready, detail = llm_status()
    if ready or not interactive:
        record("Config", "OK" if ready else "WARN", f"LLM: {detail}" + ("" if ready else " (offline tests still run)"))
        return

    grok_found = shutil.which("grok") is not None
    print("\nThe live steps need an LLM. How do you want to connect?")
    print("  1) Anthropic-compatible gateway   (paste your token)")
    print(f"  2) Grok CLI simulator             (local 'grok' CLI, {'found' if grok_found else 'NOT found'} on PATH)")
    print("  3) Skip for now                   (offline tests and the free benchmark only)")
    print("  4) Company AI gateway             (chat/completions URL + AM token or JWT)")
    choice = ask("Choose 1, 2, 3 or 4", "2" if grok_found else "3", interactive)

    if choice == "1":
        token = getpass.getpass("KM_LLM_API_TOKEN (input hidden): ").strip()
        base_url = ask("Gateway URL (empty = api.anthropic.com)", "", interactive)
        mode = ask("Auth mode: api_key or bearer", "api_key", interactive)
        if token:
            set_env({"KM_LLM_PROVIDER": "anthropic", "KM_LLM_API_TOKEN": token,
                     "KM_LLM_BASE_URL": base_url, "KM_LLM_AUTH_MODE": mode})
    elif choice == "2":
        set_env({"KM_LLM_PROVIDER": "grok_cli", "KM_GROK_EFFORT": "low"})
    elif choice == "4":
        url = ask("Chat completions URL (.../<Use Case ID>/<Provider>/<Model>/chat/completions)", "", interactive)
        auth = ask("Auth: staff (AM token) or service (JWT)", "staff", interactive)
        token = getpass.getpass("KM_GATEWAY_TOKEN (input hidden): ").strip()
        embed = ask("Embeddings URL (empty = keep local embeddings)", "", interactive)
        updates = {"KM_LLM_PROVIDER": "gateway", "KM_GATEWAY_CHAT_URL": url,
                   "KM_GATEWAY_AUTH": auth, "KM_GATEWAY_TOKEN": token}
        if embed:
            name = ask("Embedding model name (used to name the index)", embed.rstrip("/").split("/")[-2], interactive)
            updates |= {"KM_GATEWAY_EMBED_URL": embed, "KM_EMBEDDING_MODEL": f"gateway:{name}"}
        if url and token:
            set_env(updates)

    ready, detail = llm_status()
    record("Config", "OK" if ready else "WARN", f"LLM: {detail}")


def step_data() -> None:
    banner("5. Demo database and document index")
    km = [venv_python(), "-m", "km.cli"]
    run(km + ["seed"], "Seed SQLite", "data/sqlite/km.db")
    print("(first run downloads the embedding and OCR models; this can take a few minutes)")
    run(km + ["ingest"], "Index documents", "data/raw/docs -> data/chroma")


def step_tests() -> None:
    banner("6. Offline tests (no LLM calls)")
    run([venv_python(), "-m", "pytest", "-q"], "Offline tests")


def step_bench() -> None:
    banner("7. Retrieval benchmark (free, no LLM calls)")
    run([venv_python(), "-m", "km.bench", "run", "--stages", "retrieval", "--label", "onboard",
         "--fail-under", "retrieval=0.9"], "Retrieval benchmark", "report in benchmarks/runs/")


def step_smoke(offline: bool) -> bool:
    banner("8. Live question (uses the LLM)")
    ready, detail = llm_status()
    if offline or not ready:
        record("Live question", "SKIP", "--offline" if offline else detail)
        return False
    print(f"Asking via {detail}: {SMOKE_QUESTION}")
    return run([venv_python(), "-m", "km.cli", "ask", SMOKE_QUESTION], "Live question")


def step_serve(interactive: bool) -> None:
    if not interactive:
        return
    if ask("\nStart the API now and open the chat UI at http://127.0.0.1:8000/ui ? (y/n)", "n", interactive).lower() != "y":
        return
    with socket.socket() as s:
        already_running = s.connect_ex(("127.0.0.1", 8000)) == 0
    webbrowser.open("http://127.0.0.1:8000/ui")
    if already_running:
        print("Something is already serving port 8000 (an earlier `km serve`?); opened the browser on it.")
        return
    print("Starting the API. Press Ctrl+C to stop.")
    try:
        subprocess.call([str(venv_python()), "-m", "km.cli", "serve"], cwd=ROOT, env=child_env())
    except KeyboardInterrupt:
        pass


def summary() -> int:
    banner("Summary")
    for step, status, detail in results:
        print(f"  [{status:4}] {step:22} {detail}")
    failed = [s for s, st, _ in results if st == "FAIL"]
    activate = r".venv\Scripts\Activate.ps1" if WIN else "source .venv/bin/activate"
    print(f"\nNext: {activate}   then try:")
    print('  km ask "What is the daily meal expense limit?"')
    print("  km serve                          # chat UI http://127.0.0.1:8000/ui, API /docs")
    print("  python -m km.bench run --stages route,sql,e2e --workers 2   # full benchmark (costs tokens)")
    if failed:
        print(f"\n{len(failed)} step(s) failed: {', '.join(failed)}. Scroll up for the error, fix it, "
              "and re-run; finished steps are quick the second time.")
        return 1
    print("\nAll set.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--yes", "-y", action="store_true", help="never prompt; keep .env as it is")
    p.add_argument("--offline", action="store_true", help="skip steps that call an LLM")
    p.add_argument("--no-bench", action="store_true", help="skip the retrieval benchmark")
    p.add_argument("--reinstall", action="store_true", help="run pip install even if pyproject.toml is unchanged")
    args = p.parse_args()
    interactive = not args.yes and sys.stdin.isatty()
    os.chdir(ROOT)

    step_python()
    step_venv()
    if not step_install(args.reinstall):
        return summary()  # nothing else can run without the packages
    step_env(interactive)
    step_data()
    step_tests()
    if args.no_bench:
        record("Retrieval benchmark", "SKIP", "--no-bench")
    else:
        step_bench()
    step_smoke(args.offline)
    code = summary()
    step_serve(interactive)
    return code


if __name__ == "__main__":
    sys.exit(main())
