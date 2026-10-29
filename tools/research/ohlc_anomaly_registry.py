#!/usr/bin/env python3
"""State machine for source-level OHLC anomalies.

An anomaly starts OPEN. It may become VERIFIED_SOURCE_ERROR when the same
source is confirmed, but it may only become RESOLVED_WITH_EVIDENCE when an
independent source and concrete evidence are recorded.
"""
from __future__ import annotations

from typing import Any

STATES = {"OPEN", "VERIFIED_SOURCE_ERROR", "RESOLVED_WITH_EVIDENCE"}


def transition(record: dict[str, Any], new_status: str, *,
               evidence_urls: list[str] | None = None,
               independent_source: bool = False) -> dict[str, Any]:
    if new_status not in STATES:
        raise ValueError(f"unknown status: {new_status}")
    if new_status == "OPEN":
        return {**record, "status": "OPEN"}
    if not evidence_urls:
        raise ValueError("evidence_required")
    if new_status == "VERIFIED_SOURCE_ERROR":
        return {**record, "status": new_status, "evidence": list(evidence_urls)}
    if not independent_source:
        raise ValueError("independent_source_required")
    return {**record, "status": new_status, "evidence": list(evidence_urls),
            "independent_source": True}


def can_close(record: dict[str, Any]) -> bool:
    return (record.get("status") == "RESOLVED_WITH_EVIDENCE"
            and bool(record.get("evidence"))
            and bool(record.get("independent_source")))
