#!/usr/bin/env python3
"""Build an auditable event-research dataset without changing the archive.

Separates forward-PIT observations from retrospective/backfilled rows. Missing
labels remain missing; no zero-fill and no date substitution.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None


def build(events: list[dict[str, Any]], labels: dict[str, dict[str, Any]],
          default_mode: str) -> dict[str, Any]:
    rows = []
    counts: dict[str, int] = {}
    for e in events:
        requested_mode = str(e.get("observation_mode") or e.get("data_mode") or default_mode)
        mode = requested_mode
        if mode not in {"forward_pit", "retrospective_backfill", "unknown"}:
            raise ValueError(f"unsupported observation mode: {mode}")
        if mode == "retrospective_backfill" and not e.get("backfill_source"):
            mode = "unknown"
        counts[mode] = counts.get(mode, 0) + 1
        published = _ts(e.get("published_at_utc"))
        first = _ts(e.get("first_seen_at_utc"))
        updated = _ts(e.get("update_first_seen_at_utc"))
        available = max([x for x in (published, first, updated) if x], default=None)
        label = labels.get(str(e.get("event_id"))) or {}
        pit_eligible = bool(mode == "forward_pit" and published is not None and first is not None and available is not None)
        rows.append({
            "event_id": e.get("event_id"),
            "event_type": e.get("event_type"),
            "source": e.get("source"),
            "source_url": e.get("source_url"),
            "content_hash": e.get("content_hash"),
            "published_at": _iso(published),
            "first_seen_at": _iso(first),
            "available_at": _iso(available),
            "decision_at": _iso(available),
            "timestamp_precision": "second" if published else "missing",
            "observation_mode": mode,
            "backfill_status": "retrospective" if requested_mode == "retrospective_backfill" else "none",
            "pit_eligible": pit_eligible,
            "availability_status": e.get("availability_status"),
            "entry_bar_date": label.get("entry_bar_date"),
            "result_1d_date": label.get("result_1d_date"),
            "result_5d_date": label.get("result_5d_date"),
            "label_status": label.get("status", "missing_label"),
            "missing_reason": None if label else "no_readiness_label",
        })
    return {
        "research_only": True,
        "default_mode": default_mode,
        "event_count": len(rows),
        "mode_counts": counts,
        "pit_count": sum(r["pit_eligible"] for r in rows),
        "retrospective_count": sum(r["observation_mode"] == "retrospective_backfill" for r in rows),
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--events", required=True)
    p.add_argument("--readiness", required=True)
    p.add_argument("--default-mode", required=True,
                   choices=("forward_pit", "retrospective_backfill", "unknown"))
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    events = json.loads(Path(args.events).read_text(encoding="utf-8"))
    readiness = json.loads(Path(args.readiness).read_text(encoding="utf-8"))
    labels = {str(r.get("event_id")): r for r in readiness.get("events", [])}
    result = build(events, labels, args.default_mode)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("event_count", "mode_counts", "pit_count",
                                             "retrospective_count")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
