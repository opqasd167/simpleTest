"""LLM test double: runs the local Grok CLI headless to simulate the company LLM gateway.

Selected with KM_LLM_PROVIDER=grok_cli. Each call starts `grok` in single-turn mode with
no tools, in an empty temporary folder, so the agent can only answer from the prompt.
"""
import json
import logging
import shutil
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path

from pydantic import ValidationError

from km.config import Settings
from km.llm.base import LLMError, T
from km.observability import generation

log = logging.getLogger(__name__)


class GrokCliClient:
    def __init__(self, settings: Settings):
        exe = shutil.which(settings.grok_bin)
        if exe is None:
            raise LLMError(f"Grok CLI '{settings.grok_bin}' not found on PATH (set KM_GROK_BIN)")
        self._exe = exe
        self._model = settings.grok_model
        self._effort = settings.grok_effort
        self._timeout = settings.grok_timeout_s
        self._workdir = Path(tempfile.mkdtemp(prefix="km-grok-"))  # empty: no project files visible
        # running totals reported by the CLI (used by the scale eval for measured cost)
        self._lock = threading.Lock()
        self.calls = 0
        self.total_cost_usd = 0.0
        self.total_output_tokens = 0

    # ---- LLMClient interface ----
    def complete(self, system: str, user: str) -> str:
        with generation("llm.complete", self._model_name(), {"system": system, "user": user}) as gen:
            out = self._run(system, user, schema=None)
            gen.update(output=out.get("text", ""), usage_details=self._usage(out),
                       metadata={"stop_reason": out.get("stopReason")})
        return out.get("text", "")

    def structured(self, system: str, user: str, schema: type[T]) -> T:
        name = f"llm.structured.{schema.__name__}"
        with generation(name, self._model_name(), {"system": system, "user": user}) as gen:
            out = self._run(system, user, schema=schema.model_json_schema())
            payload = out.get("structuredOutput")
            try:
                if payload is None:  # fall back to parsing the text reply
                    payload = json.loads(out.get("text", ""))
                parsed = schema.model_validate(payload)
            except (ValidationError, json.JSONDecodeError) as e:
                raise LLMError(f"Grok returned output that does not match {schema.__name__}: {e}") from e
            gen.update(output=parsed.model_dump(), usage_details=self._usage(out),
                       metadata={"stop_reason": out.get("stopReason")})
        return parsed

    # ---- internals ----
    def _run(self, system: str, user: str, schema: dict | None) -> dict:
        call_id = uuid.uuid4().hex
        sys_file = self._workdir / f"{call_id}.system.txt"
        prompt_file = self._workdir / f"{call_id}.prompt.txt"
        sys_file.write_text(system, encoding="utf-8")
        prompt_file.write_text(user, encoding="utf-8")
        cmd = [self._exe, "--prompt-file", str(prompt_file), "--system-prompt-file", str(sys_file),
               "--output-format", "json", "--tools", "", "--max-turns", "3",
               "--rules", "You have no tools. Answer directly from the prompt in a single reply.",
               "--no-memory", "--no-subagents", "--disable-web-search"]
        if self._model:
            cmd += ["-m", self._model]
        if self._effort:
            cmd += ["--reasoning-effort", self._effort]
        if schema:
            cmd += ["--json-schema", json.dumps(schema)]
        try:
            proc = self._exec(cmd)
            if proc.returncode != 0:  # agent runs are occasionally flaky: retry once
                log.warning("Grok CLI failed (%s); retrying once", self._errors(proc))
                proc = self._exec(cmd)
        finally:
            sys_file.unlink(missing_ok=True)
            prompt_file.unlink(missing_ok=True)

        if proc.returncode != 0:
            raise LLMError(f"Grok CLI failed (exit {proc.returncode}): {self._errors(proc)}")
        start = proc.stdout.find("{")
        try:
            out = json.loads(proc.stdout[start:]) if start >= 0 else {}
        except json.JSONDecodeError as e:
            raise LLMError(f"Grok CLI printed invalid JSON: {proc.stdout[:300]}") from e
        with self._lock:
            self.calls += 1
            self.total_cost_usd += float(out.get("total_cost_usd") or 0)
            self.total_output_tokens += int((out.get("usage") or {}).get("output_tokens") or 0)
        if out.get("stopReason") not in (None, "end_turn"):
            log.warning("Grok stop reason: %s", out.get("stopReason"))
        return out

    def _exec(self, cmd: list[str]) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(cmd, cwd=self._workdir, capture_output=True, text=True,
                                  encoding="utf-8", timeout=self._timeout)
        except subprocess.TimeoutExpired as e:
            raise LLMError(f"Grok CLI timed out after {self._timeout:.0f}s") from e

    @staticmethod
    def _errors(proc: subprocess.CompletedProcess) -> str:
        lines = [ln for ln in proc.stderr.splitlines() if not ln.startswith("warning")]
        return " ".join(lines)[-500:]

    def _model_name(self) -> str:
        return self._model or "grok-cli-default"

    @staticmethod
    def _usage(out: dict) -> dict:
        u = out.get("usage") or {}
        return {"input_tokens": u.get("input_tokens", 0), "output_tokens": u.get("output_tokens", 0)}
