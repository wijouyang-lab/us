#!/usr/bin/env python3
"""Plan event entry/+1/+5 trading dates without fabricating returns.

Uses the NYSE calendar. Returns stay null until an approved price provider is
available. Fed historical rows remain retrospective.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import exchange_calendars as xcals
import pandas as pd


def _ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None


def _events(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return payload.get("rows") or payload.get("events") or []
    raise ValueError("event input must be a list or an object with rows/events")


def map_event(event: dict[str, Any], calendar) -> dict[str, Any]:
    published = _ts(event.get("published_at_utc") or event.get("published_at"))
    first = _ts(event.get("first_seen_at_utc") or event.get("first_seen_at"))
    updated = _ts(event.get("update_first_seen_at_utc"))
    available = max([x for x in (published, first, updated) if x], default=None)
    out = {
        "event_id": event.get("event_id") or event.get("source_event_id"),
        "published_at": _iso(published),
        "available_at": _iso(available),
        "entry_date": None,
        "entry_close_utc": None,
        "plus1_date": None,
        "plus5_date": None,
        "label_status": "pending_price_provider",
        "missing_reason": "no_approved_price_provider",
        "return_1d": None,
        "return_5d": None,
        "observation_mode": event.get("observation_mode", "retrospective_backfill"),
    }
    if available is None:
        out.update(label_status="missing_event_time", missing_reason="missing_published_at")
        return out
    sessions = calendar.sessions_in_range(
        (available.date() - timedelta(days=14)).isoformat(),
        (available.date() + timedelta(days=45)).isoformat(),
    )
    if len(sessions) == 0:
        out.update(label_status="missing_trading_session", missing_reason="no_sessions")
        return out
    schedule = calendar.schedule.loc[sessions]
    entry = None
    for session in sessions:
        close = schedule.loc[session, "close"].to_pydatetime()
        if available < close:
            entry = session
            break
    if entry is None:
        out.update(label_status="missing_trading_session", missing_reason="no_later_session")
        return out
    idx = list(sessions).index(entry)
    if idx + 5 >= len(sessions):
        out.update(label_status="missing_trading_session", missing_reason="insufficient_sessions")
        return out
    out.update({
        "entry_date": entry.date().isoformat(),
        "entry_close_utc": _iso(schedule.loc[entry, "close"].to_pydatetime()),
        "plus1_date": sessions[idx + 1].date().isoformat(),
        "plus5_date": sessions[idx + 5].date().isoformat(),
    })
    return out


def build(payload: Any, calendar=None) -> dict[str, Any]:
    calendar = calendar or xcals.get_calendar("XNYS")
    rows = [map_event(e, calendar) for e in _events(payload)]
    return {
        "research_only": True,
        "calendar": "XNYS",
        "event_count": len(rows),
        "mapped_count": sum(r["entry_date"] is not None for r in rows),
        "label_count": sum(r["return_1d"] is not None for r in rows),
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--events", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    payload = json.loads(Path(args.events).read_text(encoding="utf-8"))
    result = build(payload)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("event_count", "mapped_count", "label_count")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
