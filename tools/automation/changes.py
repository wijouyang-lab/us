"""Safe staging and diff collection for the DSH automation."""
from __future__ import annotations

import subprocess
from pathlib import Path

ALLOWED = ("docs/research", "data/research", "tools/research", "tests")


def _run(cmd, cwd, check=True):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=check)


def changed_paths(repo: Path) -> list[str]:
    p = _run(["git", "status", "--porcelain=v1", "-z"], repo)
    out = p.stdout.split("\0")
    paths = []
    i = 0
    while i < len(out):
        entry = out[i]
        i += 1
        if not entry:
            continue
        xy, path = entry[:2], entry[3:]
        if "R" in xy or "C" in xy:
            # rename/copy: next NUL is the old path
            i += 1
        if path.startswith("automation/state/") or path.startswith("automation/logs/"):
            continue
        paths.append(path)
    return sorted(set(paths))


def validate_paths(paths: list[str]) -> None:
    for p in paths:
        parts = Path(p).parts
        if Path(p).is_absolute() or ".." in parts or not any(p == a or p.startswith(a + "/") for a in ALLOWED):
            raise ValueError(f"UNAUTHORIZED_PATH:{p}")


def stage_allowed(repo: Path, paths: list[str]) -> str:
    validate_paths(paths)
    if not paths:
        return ""
    _run(["git", "add", "-A", "--"] + paths, repo)
    return _run(["git", "diff", "--cached", "--binary"], repo).stdout


def commit_diff(repo: Path) -> str:
    return _run(["git", "diff", "HEAD^", "HEAD", "--binary"], repo).stdout
