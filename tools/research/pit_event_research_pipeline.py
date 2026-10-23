"""Reproducible, research-only audit pipeline for point-in-time event inputs.

This composes already-normalized records and has no network or production hooks.
The report is an audit artifact, not a trading signal or performance claim.
"""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping

from tools.research.pit_event_archive import select_event_versions_asof
from tools.research.pit_event_coverage import audit_event_coverage
from tools.research.pit_macro_surprise import macro_surprise

PIPELINE_SCHEMA_VERSION = "1.1"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
        allow_nan=False,
    )


def _snapshot_hash(events: list[Mapping[str, Any]]) -> str:
    """Hash records independently of their input ordering."""
    serialized = sorted(_canonical_json(dict(event)) for event in events)
    return sha256(_canonical_json(serialized).encode("utf-8")).hexdigest()


def build_event_research_report(
    events: Iterable[Mapping[str, Any]],
    decision_at: str,
    *,
    max_age_by_type: Mapping[str, timedelta] | None = None,
    expected_sources: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Build deterministic integrity/coverage report for one decision timestamp.

    If the input contains a versioned event archive, first select the latest
    observed version of each event known by decision_at. The selected records
    then pass through the ordinary publication/first-seen/freshness audit.
    """
    source_rows = [dict(row) for row in events]
    versioned_rows = [bool(row.get("event_version_id")) for row in source_rows]
    if any(versioned_rows) and not all(versioned_rows):
        raise ValueError("input cannot mix versioned archive records with unversioned events")
    asof_selection_applied = bool(source_rows) and all(versioned_rows)
    rows = (
        select_event_versions_asof(source_rows, decision_at)
        if asof_selection_applied
        else source_rows
    )

    age_config = {
        str(event_type): age.total_seconds()
        for event_type, age in sorted((max_age_by_type or {}).items())
    }
    coverage = audit_event_coverage(
        rows,
        decision_at,
        max_age_by_type=max_age_by_type,
        expected_sources=expected_sources,
    )

    surprise_records: list[dict[str, Any]] = []
    surprise_reasons: dict[str, int] = {}
    for index, event in enumerate(rows):
        if str(event.get("event_type") or "") != "macro_release":
            continue
        result = macro_surprise(event, decision_at)
        reason = str(result["reason"])
        surprise_reasons[reason] = surprise_reasons.get(reason, 0) + 1
        surprise_records.append({
            "event_id": str(event.get("event_id") or event.get("source_event_id") or f"row:{index}"),
            "event_version_id": str(event.get("event_version_id") or ""),
            "eligible": bool(result["eligible"]),
            "reason": reason,
            "surprise": result.get("surprise"),
            "published_at_utc": result.get("published_at_utc"),
            "consensus_asof_utc": result.get("consensus_asof_utc"),
        })

    surprise_records.sort(key=_canonical_json)
    payload_for_hash = {
        "schema_version": PIPELINE_SCHEMA_VERSION,
        "decision_at_utc": decision_at,
        "max_age_seconds_by_type": age_config,
        "events": sorted(_canonical_json(row) for row in rows),
    }
    snapshot_hash = sha256(_canonical_json(payload_for_hash).encode("utf-8")).hexdigest()

    return {
        "pipeline_schema_version": PIPELINE_SCHEMA_VERSION,
        "decision_at_utc": decision_at,
        "input_event_count": len(source_rows),
        "asof_event_count": len(rows),
        "asof_selection_applied": asof_selection_applied,
        "source_snapshot_sha256": _snapshot_hash(source_rows),
        "input_snapshot_sha256": snapshot_hash,
        "max_age_seconds_by_type": age_config,
        "coverage_audit": coverage,
        "macro_surprise": {
            "candidate_count": len(surprise_records),
            "eligible_count": sum(record["eligible"] for record in surprise_records),
            "ineligible_count": sum(not record["eligible"] for record in surprise_records),
            "reason_counts": dict(sorted(surprise_reasons.items())),
            "records": surprise_records,
        },
        "research_only": True,
        "trading_signal_generated": False,
    }
