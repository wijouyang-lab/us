"""Sanitize and bound diagnostic text before it can enter a public artifact."""
from __future__ import annotations

import re

MAX_SUMMARY = 1200
_SENSITIVE = re.compile(r"(?i)(key|token|secret|password|authorization|bearer)")
_CREDENTIAL_VALUE = re.compile(r"(?i)(sk-[A-Za-z0-9_-]{6,}|gh[pousr]_[A-Za-z0-9]{8,}|github_pat_[A-Za-z0-9_]{8,}|Bearer\s+[A-Za-z0-9._-]{8,})")


def redact(text: str, limit: int = MAX_SUMMARY) -> str:
    if not text:
        return ""
    out = []
    for line in text.splitlines():
        if _SENSITIVE.search(line) and "=" in line:
            out.append(line.split("=", 1)[0] + "=<redacted>")
        else:
            out.append(_CREDENTIAL_VALUE.sub("<redacted>", line))
    value = "\n".join(out)
    return value[:limit] + ("\n<truncated>" if len(value) > limit else "")
