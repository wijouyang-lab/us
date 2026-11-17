"""Input validation for the DSH automation workflow."""
from __future__ import annotations

import re

TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
BRANCH_RE = re.compile(r"^(feature|fix|research|automation)/[A-Za-z0-9][A-Za-z0-9._/-]{0,119}$")


def validate_task_id(value: str) -> str:
    if not TASK_ID_RE.fullmatch(value or ""):
        raise ValueError("INVALID_TASK_ID")
    return value


def validate_branch(value: str, base: str = "main") -> str:
    v = value or ""
    if v in {"main", "master"} or v == base:
        raise ValueError("PROTECTED_BRANCH")
    if ".." in v or v.startswith("/") or v.endswith("/") or "//" in v:
        raise ValueError("INVALID_BRANCH")
    if not BRANCH_RE.fullmatch(v):
        raise ValueError("INVALID_BRANCH")
    return v


def validate_base(value: str) -> str:
    v = value or ""
    if v in {"main", "master"}:
        return v
    if ".." in v or v.startswith("/") or v.endswith("/") or "//" in v:
        raise ValueError("INVALID_BASE_BRANCH")
    if not BRANCH_RE.fullmatch(v):
        raise ValueError("INVALID_BASE_BRANCH")
    return v
