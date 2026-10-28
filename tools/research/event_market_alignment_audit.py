#!/usr/bin/env python3
"""Audit event-time to daily price-bar alignment for PIT research.

Research only. No strategy, signal, order, or production code.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

import pandas as pd

from tools.research.pit_event_archive import select_event_versions_asof
from tools.research.pit_event_eligibility import _parse_aware_timestamp

NEW_YORK = ZoneInfo("America/New_York")


def _date_only(value: Any) -> bool:
    if not isinstance(value, str) or len(value.strip()) != 10:
        return False
    try:
        date.fromisoformat(value.strip())
    except ValueError:
        return False
    return True


def _close_utc(day: date) -> datetime:
    local = datetime.combine(day, time(16, 0), tzinfo=NEW_YORK)
    return local.astimezone(timezone.utc)


def _available_at(event: Mapping[str, Any]) -> datetime | None:
    values = [
        _parse_aware_timestamp(event.get("published_at_utc")),
        _parse_aware_timestamp(event.get("first_seen_at_utc")),
        _parse_aware_timestamp(event.get("update_first_seen_at_utc")),
    ]
    values = [v for v in values if v is not None]
    return max(values) if values else None


def _entry_date(available: datetime, trading_dates: Iterable[date]) -> tuple[date | None, datetime | None]:
    """First close strictly after availability; same-day close only if before 16:00 ET."""
    for day in sorted(trading_dates):
        close = _close_utc(day)
        if close > available:
            return day, close
    return None, None


def align_events(
    events: list[Mapping[str, Any]],
    price_dates: Iterable[date],
    *,
    decision_at: str,
    tickers: Iterable[str] | None = None,
) -> dict[str, Any]:
    decision = _parse_aware_timestamp(decision_at)
    if decision is None:
        raise ValueError("decision_at must be timezone-aware ISO-8601")
    selected = select_event_versions_asof(events, decision_at) if events else []
    trading = sorted(set(price_dates))
    allowed_tickers = {str(t).upper() for t in (tickers or [])}
    rows = []
    for event in selected:
        source = str(event.get("source") or "")
        event_id = str(event.get("event_id") or "")
        source_url = str(event.get("source_url") or "")
        published_raw = event.get("published_at_utc")
        published = _parse_aware_timestamp(published_raw)
        first_seen = _parse_aware_timestamp(event.get("first_seen_at_utc"))
        event_time_raw = event.get("event_time_utc")
        event_time = _parse_aware_timestamp(event_time_raw)
        available = _available_at(event)
        entity_tickers = {str(t).upper() for t in (event.get("tickers") or [])}
        reasons = []
        if not event_id:
            reasons.append("missing_event_id")
        if not source:
            reasons.append("missing_source")
        if not source_url.startswith(("http://", "https://")):
            reasons.append("missing_or_invalid_source_url")
        if published is None:
            reasons.append("missing_or_invalid_source_published_at")
        if first_seen is None:
            reasons.append("missing_or_invalid_first_seen_at")
        if _date_only(published_raw) or _date_only(event.get("first_seen_at_utc")) or _date_only(event_time_raw):
            reasons.append("date_only_timestamp")
        if available is None:
            reasons.append("missing_available_at")
        if event_time is None:
            reasons.append("event_time_missing")
        if available and decision < available:
            reasons.append("decision_before_available")
        if allowed_tickers and entity_tickers and not (entity_tickers & allowed_tickers):
            reasons.append("ticker_mismatch")
        entry_day, entry_close = _entry_date(available, trading) if available else (None, None)
        if available and entry_day is None:
            reasons.append("no_price_bar_after_available")
        lookahead = bool(available and entry_close and entry_close <= available)
        if lookahead:
            reasons.append("entry_close_not_after_available")
        hard = {
            "missing_event_id", "missing_source", "missing_or_invalid_source_url",
            "missing_or_invalid_source_published_at", "missing_or_invalid_first_seen_at",
            "date_only_timestamp", "missing_available_at", "decision_before_available",
            "ticker_mismatch", "no_price_bar_after_available", "entry_close_not_after_available",
        }
        if any(r in hard for r in reasons):
            status = "excluded"
        elif event_time is None:
            status = "descriptive_only"
        else:
            status = "strict_pit"
        rows.append({
            "event_id": event_id or None,
            "event_type": event.get("event_type"),
            "source": source or None,
            "source_url": source_url or None,
            "entity_id": ",".join(sorted(entity_tickers)) if entity_tickers else (
                "market" if event.get("market_scope") == "market" else None
            ),
            "event_time": event_time.isoformat().replace("+00:00", "Z") if event_time else None,
            "source_published_at": published.isoformat().replace("+00:00", "Z") if published else None,
            "first_seen_at": first_seen.isoformat().replace("+00:00", "Z") if first_seen else None,
            "available_at": available.isoformat().replace("+00:00", "Z") if available else None,
            "decision_at": decision.isoformat().replace("+00:00", "Z"),
            "entry_bar_date": entry_day.isoformat() if entry_day else None,
            "entry_close_utc": entry_close.isoformat().replace("+00:00", "Z") if entry_close else None,
            "same_day_close_usable": bool(
                entry_day and available and available.date() == entry_day and _close_utc(entry_day) > available
            ),
            "lookahead_flag": lookahead,
            "timestamp_confidence": "strict" if not reasons else "partial",
            "validation_status": status,
            "validation_reasons": sorted(set(reasons)),
        })
    summary = {
        "selected_events": len(selected),
        "strict_pit": sum(r["validation_status"] == "strict_pit" for r in rows),
        "descriptive_only": sum(r["validation_status"] == "descriptive_only" for r in rows),
        "excluded": sum(r["validation_status"] == "excluded" for r in rows),
        "lookahead_flags": sum(r["lookahead_flag"] for r in rows),
        "missing_event_time": sum("event_time_missing" in r["validation_reasons"] for r in rows),
        "date_only": sum("date_only_timestamp" in r["validation_reasons"] for r in rows),
    }
    return {
        "decision_at": decision_at,
        "summary": summary,
        "events": rows,
        "research_only": True,
        "no_strategy_signal": True,
    }


def load_price_dates(path: str | Path) -> list[date]:
    df = pd.read_csv(path, usecols=["Date"])
    return sorted({pd.Timestamp(x).date() for x in df["Date"].dropna()})


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--events", required=True)
    p.add_argument("--price-panel", required=True)
    p.add_argument("--decision-at", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    events = json.loads(Path(args.events).read_text(encoding="utf-8"))
    report = align_events(events, load_price_dates(args.price_panel), decision_at=args.decision_at)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
