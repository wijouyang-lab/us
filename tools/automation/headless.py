"""Run DSH headless and persist NDJSON logs."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


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
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        timed_out = False
        try:
            output, _ = proc.communicate(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
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
