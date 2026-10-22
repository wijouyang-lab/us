#!/usr/bin/env python3
"""Load effective-dated S&P 500 membership records for research-only PIT filters."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import tempfile
from typing import Iterable


@dataclass(frozen=True, order=True)
class MembershipInterval:
    ticker: str
    date_added: date
    date_removed: date | None
    date_added_approximate: bool = False
    date_removed_approximate: bool = False


def _parse_effective_date(value: object, *, field: str, line: int) -> tuple[date | None, bool]:
    raw = str(value or "").strip()
    if not raw:
        return None, False
    approximate = "*" in raw
    normalized = raw.replace("*", "").strip()
    try:
        return date.fromisoformat(normalized), approximate
    except ValueError as exc:
        raise ValueError(f"invalid {field} on CSV line {line}: {raw!r}") from exc


def load_membership_history(path: str | Path) -> dict[str, list[MembershipInterval]]:
    """Load all membership spans; duplicate symbols are retained as separate spans.

    date_added is inclusive. date_removed is exclusive: the ticker is not considered
    an index member on or after the effective removal date. Upstream '*' markers are
    recorded as approximation metadata instead of silently discarded.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        field_map = {str(name or "").strip().lower(): name for name in (reader.fieldnames or [])}
        ticker_field = field_map.get("symbol") or field_map.get("ticker")
        added_field = field_map.get("date_added")
        removed_field = field_map.get("date_removed")
        if not ticker_field or not added_field or not removed_field:
            raise ValueError(
                "membership CSV must contain symbol/ticker, date_added, and date_removed columns"
            )

        grouped: dict[str, list[MembershipInterval]] = {}
        for line, row in enumerate(reader, start=2):
            ticker = str(row.get(ticker_field) or "").strip().upper()
            if not ticker:
                raise ValueError(f"empty ticker on CSV line {line}")
            added, added_approx = _parse_effective_date(
                row.get(added_field), field="date_added", line=line
            )
            removed, removed_approx = _parse_effective_date(
                row.get(removed_field), field="date_removed", line=line
            )
            if added is None:
                raise ValueError(f"missing date_added on CSV line {line} for {ticker}")
            if removed is not None and removed <= added:
                raise ValueError(
                    f"date_removed must be later than date_added on CSV line {line} for {ticker}"
                )
            grouped.setdefault(ticker, []).append(
                MembershipInterval(ticker, added, removed, added_approx, removed_approx)
            )

    if not grouped:
        raise ValueError("membership CSV contains no membership rows")
    for ticker in grouped:
        grouped[ticker].sort(key=lambda interval: (interval.date_added, interval.date_removed or date.max))
    return grouped


def is_member_on(
    ticker: str,
    when: date,
    history: dict[str, list[MembershipInterval]],
) -> bool:
    ticker = str(ticker).strip().upper()
    return any(
        interval.date_added <= when
        and (interval.date_removed is None or when < interval.date_removed)
        for interval in history.get(ticker, ())
    )


def active_tickers_on(
    when: date, history: dict[str, list[MembershipInterval]]
) -> set[str]:
    return {
        ticker
        for ticker, intervals in history.items()
        if any(
            interval.date_added <= when
            and (interval.date_removed is None or when < interval.date_removed)
            for interval in intervals
        )
    }


def tickers_overlapping(
    start: date, end: date, history: dict[str, list[MembershipInterval]]
) -> set[str]:
    """Tickers with at least one membership span intersecting [start, end]."""
    return {
        ticker
        for ticker, intervals in history.items()
        if any(
            interval.date_added <= end
            and (interval.date_removed is None or interval.date_removed > start)
            for interval in intervals
        )
    }


def approximate_date_counts(history: dict[str, list[MembershipInterval]]) -> dict[str, int]:
    intervals: Iterable[MembershipInterval] = (
        interval for rows in history.values() for interval in rows
    )
    rows = list(intervals)
    return {
        "membership_intervals": len(rows),
        "approximate_date_added": sum(row.date_added_approximate for row in rows),
        "approximate_date_removed": sum(row.date_removed_approximate for row in rows),
    }



def _normalise_cik(value: object) -> str:
    raw = str(value or "").strip()
    digits = "".join(char for char in raw if char.isdigit())
    return digits.lstrip("0") or "0" if digits else ""


def load_membership_history_with_aliases(
    path: Path,
    aliases_path: Path,
    alias_usage: dict | None = None,
):
    """Load membership intervals after CIK-guarded same-security ticker canonicalization.

    The historical source can contain overlapping rows for a company's former and
    replacement ticker. The alias registry only rewrites a source ticker when both
    the ticker and SEC CIK match. This is important for reused symbols such as ARNC.
    It does not map acquirers to acquired companies or span a merger into a different
    security. The regular loader remains responsible for date/schema validation.
    """
    path = Path(path)
    aliases_path = Path(aliases_path)
    with aliases_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required_alias_columns = {"old_ticker", "canonical_ticker", "cik", "source_url", "change_type"}
        actual_alias_columns = {str(name or "").strip().lower() for name in (reader.fieldnames or [])}
        if not required_alias_columns.issubset(actual_alias_columns):
            raise ValueError(
                f"ticker alias registry missing columns: {sorted(required_alias_columns - actual_alias_columns)}"
            )
        alias_map: dict[tuple[str, str], str] = {}
        for row in reader:
            normalized = {str(key or "").strip().lower(): str(value or "").strip() for key, value in row.items()}
            old_ticker = normalized.get("old_ticker", "").upper()
            canonical_ticker = normalized.get("canonical_ticker", "").upper()
            cik = _normalise_cik(normalized.get("cik", ""))
            source_url = normalized.get("source_url", "")
            if not old_ticker or not canonical_ticker or old_ticker == canonical_ticker or not cik:
                raise ValueError(f"invalid ticker alias row: {normalized}")
            if not source_url.startswith("https://"):
                raise ValueError(f"ticker alias source_url must use HTTPS: {normalized}")
            key = (old_ticker, cik)
            prior = alias_map.get(key)
            if prior is not None and prior != canonical_ticker:
                raise ValueError(f"conflicting ticker aliases for {key}: {prior} vs {canonical_ticker}")
            alias_map[key] = canonical_ticker

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        lowered_columns = {str(name or "").strip().lower() for name in fieldnames}
        if "symbol" not in lowered_columns or "cik" not in lowered_columns:
            raise ValueError("historical membership source must contain symbol and cik columns")
        symbol_column = next(name for name in fieldnames if name.strip().lower() == "symbol")
        cik_column = next(name for name in fieldnames if name.strip().lower() == "cik")
        rows = list(reader)

    matched_aliases: set[tuple[str, str]] = set()
    applied: dict[str, str] = {}
    for row in rows:
        old_ticker = str(row.get(symbol_column) or "").strip().upper()
        cik = _normalise_cik(row.get(cik_column))
        key = (old_ticker, cik)
        canonical_ticker = alias_map.get(key)
        if canonical_ticker:
            row[symbol_column] = canonical_ticker
            matched_aliases.add(key)
            applied[old_ticker] = canonical_ticker

    unmatched = sorted(set(alias_map) - matched_aliases)
    if unmatched:
        examples = [{"old_ticker": ticker, "cik": cik, "expected_canonical": alias_map[(ticker, cik)]} for ticker, cik in unmatched[:20]]
        raise ValueError(
            f"{len(unmatched)} alias registry entries did not match a source ticker+CIK row; examples={examples}"
        )

    with tempfile.TemporaryDirectory(prefix="pit-membership-alias-") as tmpdir:
        normalized_path = Path(tmpdir) / path.name
        with normalized_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
            writer.writeheader()
            writer.writerows(rows)
        history = load_membership_history(normalized_path)

    if alias_usage is not None:
        alias_usage.clear()
        alias_usage.update({
            "registry_rows": len(alias_map),
            "applied_source_symbols": sorted(applied.items()),
            "applied_source_symbol_count": len(applied),
            "source_membership_rows": len(rows),
            "canonical_symbol_count": len(history),
        })
    return history
