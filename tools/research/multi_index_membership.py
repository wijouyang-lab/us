"""Combine point-in-time membership histories for S&P 500, Nasdaq-100 and Dow 30.

The S&P source uses the repository's CIK-guarded alias registry. Nasdaq/Dow inputs
are research-grade interval datasets retained with their upstream MIT license.
Coverage is unioned by ticker and session; overlapping index membership never counts
the same ticker-session twice.
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

try:
    from .pit_membership import MembershipInterval, load_membership_history_with_aliases
except ImportError:  # direct script execution from tools/research
    from pit_membership import MembershipInterval, load_membership_history_with_aliases


def _load_interval_csv(path: Path) -> dict[str, list[MembershipInterval]]:
    grouped: dict[str, list[MembershipInterval]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = {str(name or "").strip().lower(): name for name in (reader.fieldnames or [])}
        symbol_field = fields.get("symbol")
        start_field = fields.get("opt-in")
        end_field = fields.get("opt-out")
        if not symbol_field or not start_field or not end_field:
            raise ValueError(f"{path} must contain symbol,opt-in,opt-out columns")
        for line, row in enumerate(reader, start=2):
            ticker = str(row.get(symbol_field) or "").strip().upper()
            try:
                start = date.fromisoformat(str(row.get(start_field) or "").strip())
                end_raw = str(row.get(end_field) or "").strip()
                end = date.fromisoformat(end_raw) if end_raw else None
            except ValueError as exc:
                raise ValueError(f"invalid membership date in {path} line {line}") from exc
            if not ticker or (end is not None and end <= start):
                raise ValueError(f"invalid membership interval in {path} line {line}")
            grouped.setdefault(ticker, []).append(MembershipInterval(ticker, start, end))
    return grouped


def load_multi_index_membership(
    sp500_path: Path,
    aliases_path: Path,
    nasdaq100_path: Path,
    dow30_path: Path,
) -> dict[str, list[MembershipInterval]]:
    """Return deduplicable per-ticker membership intervals from all three indices."""
    combined = load_membership_history_with_aliases(sp500_path, aliases_path)
    for source in (nasdaq100_path, dow30_path):
        for ticker, intervals in _load_interval_csv(source).items():
            combined.setdefault(ticker, []).extend(intervals)
    for ticker, intervals in combined.items():
        combined[ticker] = sorted(
            set(intervals),
            key=lambda item: (item.date_added, item.date_removed or date.max),
        )
    return combined
