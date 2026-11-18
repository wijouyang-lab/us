"""Run DSH headless with a scrubbed child environment and bounded streaming output."""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import threading
from pathlib import Path

BASE_ALLOW = {
    "PATH", "HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA",
    "SYSTEMROOT", "WINDIR", "TMP", "TEMP", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE",
    "TERM", "SHELL", "USER", "LOGNAME", "PYTHONPATH",
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy",
    "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL", "DSH_HOME",
}
MODEL_AUTH = {"DEEPSEEK_API_KEY"}
MAX_OUTPUT_BYTES = 200_000


def child_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k in BASE_ALLOW}
    for k, v in (extra or {}).items():
        if not any(x in k.upper() for x in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            env[k] = v
    for k in MODEL_AUTH:
        if os.environ.get(k):
            env[k] = os.environ[k]
    for k in ("GH_TOKEN", "GITHUB_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "CODEX_CMD"):
        env.pop(k, None)
    return env


def _kill_tree(proc: subprocess.Popen, pgid: int | None = None) -> None:
    if os.name != "nt":
        try:
            os.killpg(pgid or os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass
    else:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    try:
        proc.kill()
    except OSError:
        pass


class HeadlessRunner:
    def __init__(self, dsh_cmd: list[str] | None = None, timeout: int = 1800, max_output_bytes: int = MAX_OUTPUT_BYTES, extra_env: dict[str, str] | None = None):
        self.extra_env = extra_env
        if dsh_cmd is None:
            binary = shutil.which("dsh") or shutil.which("dsh.cmd") or "dsh"
            dsh_cmd = [binary, "--profile", "headless", "--json"]
        self.dsh_cmd = dsh_cmd
        self.timeout = timeout
        self.max_output_bytes = max_output_bytes

    def run(self, prompt: str, log_path: Path) -> dict:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = self.dsh_cmd + [prompt]
        kwargs = {"start_new_session": True} if os.name != "nt" else {}
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=child_env(self.extra_env), **kwargs,
        )
        pgid = None
        if os.name != "nt":
            try:
                pgid = os.getpgid(proc.pid)
            except OSError:
                pgid = None
        chunks: list[bytes] = []
        total = 0
        exceeded = False
        lock = threading.Lock()

        def _reader():
            nonlocal total, exceeded
            while True:
                chunk = proc.stdout.read(4096) if proc.stdout else b""
                if not chunk:
                    break
                with lock:
                    if total >= self.max_output_bytes:
                        exceeded = True
                        _kill_tree(proc, pgid)
                        break
                    keep = chunk[: self.max_output_bytes - total]
                    chunks.append(keep)
                    total += len(keep)
                    if len(chunk) > len(keep):
                        exceeded = True
                        _kill_tree(proc, pgid)
                        break

        thread = threading.Thread(target=_reader, daemon=True)
        thread.start()
        timed_out = False
        try:
            proc.wait(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_tree(proc, pgid)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _kill_tree(proc, pgid)
        _kill_tree(proc, pgid)
        thread.join(timeout=5)
        reader_alive = thread.is_alive()
        try:
            if proc.stdout:
                proc.stdout.close()
        except OSError:
            pass
        output = b"".join(chunks).decode("utf-8", errors="replace")
        if not exceeded:
            output = output[: self.max_output_bytes]
        log_path.write_text(output, encoding="utf-8")
        final = None
        session_id = None
        for line in output.splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "session":
                session_id = ev.get("sessionId")
            if ev.get("type") == "final":
                final = ev.get("text", "")
        if exceeded:
            rc = 125
        elif timed_out:
            rc = 124
        elif reader_alive:
            rc = 126
        else:
            rc = proc.returncode
        return {"returncode": rc, "final": final, "session_id": session_id, "log": str(log_path), "timed_out": timed_out, "output_limit_exceeded": exceeded, "cleanup_failed": reader_alive, "final_event": final is not None}
