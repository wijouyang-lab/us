#!/usr/bin/env python3
"""Plan event entry/+1/+5 trading dates without fabricating returns.

Default entry rule is conservative: an event before the session open can enter
at that open; an event at/after the open enters at the next session open.
The legacy same-day-close rule is retained only for comparison.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import exchange_calendars as xcals


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


def map_event(event: dict[str, Any], calendar, entry_rule: str = "next_open") -> dict[str, Any]:
    published = _ts(event.get("published_at_utc") or event.get("published_at"))
    first = _ts(event.get("first_seen_at_utc") or event.get("first_seen_at"))
    updated = _ts(event.get("update_first_seen_at_utc"))
    decision = _ts(event.get("decision_at") or event.get("decision_at_utc"))
    mode = event.get("observation_mode", "retrospective_backfill")
    invalid_reason = None
    if published is None:
        available = None
        availability_known = False
        mapping_time = None
        availability_basis = "missing_publication"
        invalid_reason = ("missing_event_time", "missing_published_at")
    elif mode == "forward_pit":
        if first is None:
            available = None
            availability_known = False
            mapping_time = None
            availability_basis = "missing_first_seen"
            invalid_reason = ("missing_event_time", "missing_first_seen_at")
        else:
            available = max([x for x in (published, first, updated) if x], default=None)
            availability_known = available is not None
            availability_basis = "pit_first_seen"
            if decision is None:
                mapping_time = None
                invalid_reason = ("missing_decision_time", "missing_decision_at")
            elif available is not None and decision < available:
                mapping_time = None
                invalid_reason = ("invalid_decision_time", "decision_before_available")
            else:
                mapping_time = decision
    else:
        available = None
        availability_known = False
        mapping_time = published
        availability_basis = "retrospective_publication_only"
    out = {
        "event_id": event.get("event_id") or event.get("source_event_id"),
        "published_at": _iso(published),
        "first_seen_at": _iso(first),
        "available_at": _iso(available),
        "decision_at": _iso(decision),
        "availability_known": availability_known,
        "availability_basis": availability_basis,
        "mapping_time": _iso(mapping_time),
        "decision_after_available": bool(decision is not None and available is not None and decision >= available),
        "plan_type": "pit_planned_entry" if mode == "forward_pit" else "retrospective_counterfactual",
        "counterfactual": mode != "forward_pit",
        "entry_date": None,
        "entry_time_utc": None,
        "entry_price_point": "open" if entry_rule == "next_open" else "close",
        "plus1_date": None,
        "plus5_date": None,
        "label_status": "pending_price_provider",
        "missing_reason": "no_approved_price_provider",
        "return_1d": None,
        "return_5d": None,
        "observation_mode": mode,
        "entry_rule": entry_rule,
    }
    if invalid_reason:
        out.update(label_status=invalid_reason[0], missing_reason=invalid_reason[1])
        return out
    if mapping_time is None:
        out.update(label_status="missing_event_time", missing_reason="missing_mapping_time")
        return out
    sessions = calendar.sessions_in_range(
        (mapping_time.date() - timedelta(days=14)).isoformat(),
        (mapping_time.date() + timedelta(days=45)).isoformat(),
    )
    if len(sessions) == 0:
        out.update(label_status="missing_trading_session", missing_reason="no_sessions")
        return out
    schedule = calendar.schedule.loc[sessions]
    entry = None
    for session in sessions:
        opens = schedule.loc[session, "open"].to_pydatetime()
        closes = schedule.loc[session, "close"].to_pydatetime()
        if entry_rule == "legacy_close":
            if mapping_time < closes:
                entry = session
                break
        else:
            if mapping_time < opens:
                entry = session
                break
    if entry is None:
        out.update(label_status="missing_trading_session", missing_reason="no_later_session")
        return out
    idx = list(sessions).index(entry)
    if idx + 5 >= len(sessions):
        out.update(label_status="missing_trading_session", missing_reason="insufficient_sessions")
        return out
    point = "close" if entry_rule == "legacy_close" else "open"
    entry_time = schedule.loc[entry, point].to_pydatetime()
    out.update({
        "entry_date": entry.date().isoformat(),
        "entry_time_utc": _iso(entry_time),
        "plus1_date": sessions[idx + 1].date().isoformat(),
        "plus5_date": sessions[idx + 5].date().isoformat(),
    })
    return out


def build(payload: Any, calendar=None, entry_rule: str = "next_open") -> dict[str, Any]:
    if entry_rule not in {"next_open", "legacy_close"}:
        raise ValueError("entry_rule must be next_open or legacy_close")
    calendar = calendar or xcals.get_calendar("XNYS")
    rows = [map_event(e, calendar, entry_rule) for e in _events(payload)]
    return {
        "research_only": True,
        "calendar": "XNYS",
        "entry_rule": entry_rule,
        "event_count": len(rows),
        "mapped_count": sum(r["entry_date"] is not None for r in rows),
        "label_count": sum(r["return_1d"] is not None for r in rows),
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--events", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--entry-rule", choices=("next_open", "legacy_close"), default="next_open")
    args = p.parse_args(argv)
    payload = json.loads(Path(args.events).read_text(encoding="utf-8"))
    result = build(payload, entry_rule=args.entry_rule)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("event_count", "mapped_count", "label_count",
                                             "entry_rule")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
