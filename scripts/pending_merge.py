"""Append-only handling for daily Scan pending files.

A same-day rerun must never truncate prior recommendations or statuses.
"""
from __future__ import annotations

import csv
import shutil
from pathlib import Path
from typing import Iterable, Mapping


def unseen_pending_items(path: str | Path, candidates: Iterable[Mapping], expected_columns: list[str] | None = None) -> list[Mapping]:
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
            if expected_columns is not None and reader.fieldnames != expected_columns:
                raise ValueError(
                    f"pending CSV schema mismatch: {target}; "
                    f"expected {expected_columns!r}, found {reader.fieldnames!r}"
                )
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


def ensure_pending_schema(path: str | Path, expected_columns: list[str]) -> list[str]:
    """Migrate an existing pending CSV to the current header without losing old data.

    Existing columns and row values are preserved. New columns are added with empty
    values for historical rows. A one-time byte-for-byte backup is retained before
    atomic replacement. Returns the resulting header, including legacy extra columns.
    """
    target = Path(path)
    if not target.exists():
        return list(expected_columns)

    with target.open("r", newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        old_columns = list(reader.fieldnames or [])
        rows = list(reader)

    if not old_columns or "Ticker" not in old_columns:
        raise ValueError(f"pending CSV has no Ticker column: {target}")
    if len(set(old_columns)) != len(old_columns):
        raise ValueError(f"pending CSV has duplicate column names: {target}")
    if old_columns == expected_columns:
        return list(expected_columns)

    # Keep the current canonical schema first, then retain any legacy-only columns.
    columns = list(expected_columns) + [c for c in old_columns if c not in expected_columns]
    backup = target.with_suffix(target.suffix + ".pre-schema-migration.bak")
    if not backup.exists():
        shutil.copy2(target, backup)

    tmp = target.with_suffix(target.suffix + ".schema-migration.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})
    tmp.replace(target)
    return columns
