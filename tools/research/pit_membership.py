#!/usr/bin/env python3
"""Load effective-dated S&P 500 membership records for research-only PIT filters."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
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
