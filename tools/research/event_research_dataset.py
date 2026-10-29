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

from tools.research.pit_admission import admit


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
          default_mode: str, evidence: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    evidence = evidence or {}
    rows = []
    counts: dict[str, int] = {}
    for e in events:
        event_id = str(e.get("event_id"))
        requested_mode = str(e.get("observation_mode") or e.get("data_mode") or default_mode)
        if requested_mode == "retrospective_backfill" and not e.get("backfill_source"):
            mode = "unknown"
        else:
            mode = requested_mode
        if mode not in {"forward_pit", "retrospective_backfill", "unknown"}:
            raise ValueError(f"unsupported observation mode: {mode}")
        ev = evidence.get(event_id) or {}
        if mode == "forward_pit" and not ev:
            mode = "unknown"
        counts[mode] = counts.get(mode, 0) + 1

        published = _ts(e.get("published_at_utc"))
        first = _ts(e.get("first_seen_at_utc"))
        updated = _ts(e.get("update_first_seen_at_utc"))
        captured = _ts(ev.get("captured_at"))
        available = max([x for x in (published, first, updated) if x], default=None)
        label = labels.get(event_id) or {}
        reasons = []
        if mode != "forward_pit":
            reasons.append("not_forward_pit")
        if not ev:
            reasons.append("missing_capture_evidence")
        if published is None:
            reasons.append("missing_published_at")
        if first is None:
            reasons.append("missing_first_seen_at")
        if captured is None:
            reasons.append("missing_capture_time")
        if first and published and first < published:
            reasons.append("first_seen_before_published")
        if first and captured and first > captured:
            reasons.append("first_seen_after_capture_record")
        if available is None:
            reasons.append("missing_available_at")
        if first and available and available < first:
            reasons.append("available_before_first_seen")
        admission = {"admitted": False, "reasons": []}
        if mode == "forward_pit":
            admission = admit({
                "event_id": event_id,
                "published_at": _iso(published),
                "first_seen_at_utc": _iso(first),
                "research_ready_at_utc": e.get("research_ready_at_utc"),
                "decision_at_utc": e.get("decision_at_utc"),
                "parse_status": e.get("parse_status"),
                "source_evidence": e.get("source_evidence"),
                "published_at_evidence": e.get("published_at_evidence"),
                "decision_evidence": e.get("decision_evidence"),
                "is_simulated": e.get("is_simulated"),
                "is_historical_backfill": e.get("is_historical_backfill"),
                "observation_kind": e.get("observation_kind"),
                "pit_status": e.get("pit_status"),
            })
            reasons.extend(r for r in admission["reasons"] if r not in reasons)
        pit_eligible = bool(admission["admitted"]) and not reasons
        decision = _ts(e.get("decision_at_utc"))
        rows.append({
            "event_id": event_id,
            "event_type": e.get("event_type"),
            "source": e.get("source"),
            "source_url": e.get("source_url"),
            "content_hash": e.get("content_hash"),
            "published_at": _iso(published),
            "first_seen_at": _iso(first),
            "available_at": _iso(available),
            "decision_at": _iso(decision),
            "decision_after_available": bool(decision is not None and available is not None and decision >= available),
            "timestamp_precision": "second" if published else "missing",
            "observation_mode": mode,
            "backfill_status": "retrospective" if requested_mode == "retrospective_backfill" else "none",
            "capture_evidence": ev,
            "pit_eligible": pit_eligible,
            "pit_reasons": reasons,
            "admission_reasons": admission["reasons"],
            "availability_status": e.get("availability_status"),
            "has_entry": bool(label.get("entry_bar_date")),
            "has_plus1": bool(label.get("result_1d_date")),
            "has_plus5": bool(label.get("result_5d_date")),
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
        "entry_count": sum(r["has_entry"] for r in rows),
        "plus1_count": sum(r["has_plus1"] for r in rows),
        "plus5_count": sum(r["has_plus5"] for r in rows),
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--events", required=True)
    p.add_argument("--readiness", required=True)
    p.add_argument("--default-mode", required=True,
                    choices=("forward_pit", "retrospective_backfill", "unknown"))
    p.add_argument("--evidence", help="JSON map event_id -> capture evidence")
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    events = json.loads(Path(args.events).read_text(encoding="utf-8"))
    readiness = json.loads(Path(args.readiness).read_text(encoding="utf-8"))
    labels = {str(r.get("event_id")): r for r in readiness.get("events", [])}
    evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8")) if args.evidence else {}
    result = build(events, labels, args.default_mode, evidence)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("event_count", "mode_counts", "pit_count",
                                             "retrospective_count", "entry_count",
                                             "plus1_count", "plus5_count")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
