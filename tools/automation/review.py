"""Independent Codex review adapter.

The reviewer must be a different actor from the DSH author. No merge approval is
issued by this module.
"""
from __future__ import annotations

import json
import shlex
import subprocess

VALID = {"PASS", "FAIL", "NEEDS_REVISION", "BLOCKED"}


def run_review(diff: str, task: str, author: str = "dsh", reviewer: str = "codex", cmd: str | None = None) -> dict:
    if author == reviewer:
        return {"status": "NEEDS_REVISION", "reason": "SELF_REVIEW_FORBIDDEN", "reviewer": reviewer}
    if not diff.strip():
        return {"status": "NEEDS_REVISION", "reason": "EMPTY_DIFF", "reviewer": reviewer}
    cmd = cmd or __import__("os").environ.get("CODEX_CMD", "")
    if not cmd:
        return {"status": "BLOCKED", "reason": "REVIEWER_UNAVAILABLE", "reviewer": reviewer}
    payload = json.dumps({"task": task, "diff": diff})
    argv = cmd if isinstance(cmd, list) else shlex.split(cmd)
    proc = subprocess.run(argv, input=payload, text=True, capture_output=True, timeout=900)
    if proc.returncode != 0:
        return {"status": "NEEDS_REVISION", "reason": "REVIEWER_ERROR", "reviewer": reviewer, "output": proc.stdout[-2000:] + proc.stderr[-2000:]}
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"status": "NEEDS_REVISION", "reason": "REVIEWER_INVALID_JSON", "reviewer": reviewer}
    status = out.get("status")
    if status not in VALID:
        return {"status": "NEEDS_REVISION", "reason": "INVALID_REVIEW_STATUS", "reviewer": reviewer}
    return {"status": status, "reason": out.get("reason", ""), "reviewer": reviewer, "summary": out.get("summary", "")}
