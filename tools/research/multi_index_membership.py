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


def _normalise_cik(value: object) -> str:
    digits = "".join(char for char in str(value or "") if char.isdigit())
    return digits.lstrip("0") or "0" if digits else ""


def _source_alias_intervals(
    sp500_path: Path, aliases_path: Path
) -> dict[str, list[tuple[date, date | None, str]]]:
    """Return date-bounded aliases grounded in S&P ticker+CIK rows.

    Nasdaq/Dow membership files do not carry CIKs. Apply a CIK-validated alias
    only during dates where the S&P source ties that old ticker to the alias CIK.
    """
    with aliases_path.open("r", encoding="utf-8-sig", newline="") as handle:
        aliases = csv.DictReader(handle)
        fields = {str(name or "").strip().lower(): name for name in (aliases.fieldnames or [])}
        old_field, canonical_field, cik_field = (
            fields.get("old_ticker"), fields.get("canonical_ticker"), fields.get("cik")
        )
        if not old_field or not canonical_field or not cik_field:
            raise ValueError("ticker alias registry must contain old_ticker, canonical_ticker, and cik")
        alias_map = {
            (str(row.get(old_field) or "").strip().upper(), _normalise_cik(row.get(cik_field))):
            str(row.get(canonical_field) or "").strip().upper()
            for row in aliases
        }

    with sp500_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = {str(name or "").strip().lower(): name for name in (reader.fieldnames or [])}
        symbol_field, cik_field = fields.get("symbol"), fields.get("cik")
        added_field, removed_field = fields.get("date_added"), fields.get("date_removed")
        if not all((symbol_field, cik_field, added_field, removed_field)):
            raise ValueError("S&P history must contain symbol, cik, date_added, and date_removed")
        result: dict[str, list[tuple[date, date | None, str]]] = {}
        for row in reader:
            old = str(row.get(symbol_field) or "").strip().upper()
            canonical = alias_map.get((old, _normalise_cik(row.get(cik_field))))
            if not canonical:
                continue
            added_raw = str(row.get(added_field) or "").replace("*", "").strip()
            removed_raw = str(row.get(removed_field) or "").replace("*", "").strip()
            added = date.fromisoformat(added_raw)
            removed = date.fromisoformat(removed_raw) if removed_raw else None
            result.setdefault(old, []).append((added, removed, canonical))
    return result


def _canonicalize_index_interval(
    interval: MembershipInterval,
    aliases: dict[str, list[tuple[date, date | None, str]]],
) -> list[MembershipInterval]:
    """Split index intervals at alias boundaries; preserve reused symbols."""
    candidates = aliases.get(interval.ticker, [])
    if not candidates:
        return [interval]
    start = interval.date_added
    end = interval.date_removed or date.max
    boundaries = {start, end}
    for alias_start, alias_end, _ in candidates:
        alias_stop = alias_end or date.max
        if alias_start < end and alias_stop > start:
            boundaries.add(max(start, alias_start))
            boundaries.add(min(end, alias_stop))
    ordered = sorted(boundaries)
    result = []
    for seg_start, seg_end in zip(ordered, ordered[1:]):
        if seg_start >= seg_end:
            continue
        mapped = {
            canonical for alias_start, alias_end, canonical in candidates
            if alias_start <= seg_start and seg_start < (alias_end or date.max)
        }
        ticker = next(iter(mapped)) if len(mapped) == 1 else interval.ticker
        result.append(MembershipInterval(
            ticker=ticker,
            date_added=seg_start,
            date_removed=None if seg_end == date.max else seg_end,
            date_added_approximate=interval.date_added_approximate,
            date_removed_approximate=interval.date_removed_approximate,
        ))
    return result or [interval]


def load_multi_index_membership(
    sp500_path: Path,
    aliases_path: Path,
    nasdaq100_path: Path,
    dow30_path: Path,
) -> dict[str, list[MembershipInterval]]:
    """Return deduplicable per-ticker membership intervals from all three indices."""
    combined = load_membership_history_with_aliases(sp500_path, aliases_path)
    # Nasdaq/Dow snapshots have no CIK column. Reuse the CIK-guarded S&P alias
    # registry only over date ranges where the S&P source confirms the old issuer.
    alias_intervals = _source_alias_intervals(sp500_path, aliases_path)
    for source in (nasdaq100_path, dow30_path):
        for ticker, intervals in _load_interval_csv(source).items():
            for interval in intervals:
                for normalized in _canonicalize_index_interval(interval, alias_intervals):
                    combined.setdefault(normalized.ticker, []).append(normalized)
    for ticker, intervals in combined.items():
        combined[ticker] = sorted(
            set(intervals),
            key=lambda item: (item.date_added, item.date_removed or date.max),
        )
    return combined
