"""Append-only handling for daily Scan pending files.

A same-day rerun must never truncate prior recommendations or statuses.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Mapping


def unseen_pending_items(path: str | Path, candidates: Iterable[Mapping]) -> list[Mapping]:
    """Return first-seen ticker candidates not already present in a pending CSV.

    Existing rows are never modified. A malformed existing file raises instead of
    silently treating it as empty, allowing the caller to fail closed.
    """
    target = Path(path)
    seen: set[str] = set()
    if target.exists():
        with target.open("r", newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames or "Ticker" not in reader.fieldnames:
                raise ValueError(f"pending CSV has no Ticker column: {target}")
            for row in reader:
                ticker = str(row.get("Ticker", "")).strip().upper()
                if ticker:
                    seen.add(ticker)

    result = []
    for item in candidates:
        ticker = str(item.get("Ticker", "")).strip().upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        result.append(item)
    return result
