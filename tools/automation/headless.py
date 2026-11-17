"""Run DSH headless with a scrubbed child environment and persisted logs."""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
from pathlib import Path

# Only launch/runtime facts needed by DSH. GitHub write credentials are never
# included; DSH's own subprocess tool also scrubs credential-shaped names.
BASE_ALLOW = {
    "PATH", "HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA",
    "SYSTEMROOT", "WINDIR", "TMP", "TEMP", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE",
    "TERM", "SHELL", "USER", "LOGNAME", "PYTHONPATH",
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy",
    "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL", "DSH_HOME",
}
MODEL_AUTH = {"DEEPSEEK_API_KEY"}


def child_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k in BASE_ALLOW}
    # Model auth is provided only to the DSH process. DSH subprocess tools scrub
    # credential-shaped variables before spawning shell commands.
    for k in MODEL_AUTH:
        if os.environ.get(k):
            env[k] = os.environ[k]
    # Explicitly drop all GitHub write credentials.
    for k in ("GH_TOKEN", "GITHUB_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "CODEX_CMD"):
        env.pop(k, None)
    return env


class HeadlessRunner:
    def __init__(self, dsh_cmd: list[str] | None = None, timeout: int = 1800):
        if dsh_cmd is None:
            binary = shutil.which("dsh") or shutil.which("dsh.cmd") or "dsh"
            dsh_cmd = [binary, "--profile", "headless", "--json"]
        self.dsh_cmd = dsh_cmd
        self.timeout = timeout

    def run(self, prompt: str, log_path: Path) -> dict:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = self.dsh_cmd + [prompt]
        kwargs = {"start_new_session": True} if os.name != "nt" else {}
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", env=child_env(), **kwargs,
        )
        timed_out = False
        try:
            output, _ = proc.communicate(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name != "nt":
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                proc.kill()
            try:
                output, _ = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                output, _ = proc.communicate()
        log_path.write_text(output or "", encoding="utf-8")
        final = None
        session_id = None
        for line in (output or "").splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "session":
                session_id = ev.get("sessionId")
            if ev.get("type") == "final":
                final = ev.get("text", "")
        rc = 124 if timed_out else proc.returncode
        return {"returncode": rc, "final": final, "session_id": session_id, "log": str(log_path), "timed_out": timed_out, "final_event": final is not None}
