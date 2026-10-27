# -*- coding: utf-8 -*-
"""Guard: repo text files must be valid UTF-8 (Pages/Jekyll build breaks otherwise)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTS = {".md", ".html", ".css", ".js", ".json", ".py", ".yml", ".yaml", ".txt", ".csv"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".pytest_cache"}


def _files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix.lower() in EXTS:
                yield p


def test_text_files_are_utf8():
    bad = []
    for p in _files():
        try:
            p.read_bytes().decode("utf-8")
        except UnicodeDecodeError as exc:
            bad.append(f"{p.relative_to(ROOT)}: {exc}")
    assert not bad, "non-UTF8 files:\n" + "\n".join(bad[:10])
