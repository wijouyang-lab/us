#!/usr/bin/env python3
"""Fail-closed contract for recent-panel fallback rows.

This module does not fetch or write data. It evaluates whether a fallback row
may be used when the primary provider returns an invalid daily bar.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping


def _invalid_ohlc(row: Mapping[str, Any]) -> bool:
    try:
        o, h, l, c = (float(row[k]) for k in ("Open", "High", "Low", "Close"))
    except (KeyError, TypeError, ValueError):
        return True
    if min(o, h, l, c) <= 0:
        return True
    return not (h >= max(o, c, l) and l <= min(o, c, h))


def _valid_date(value: Any) -> bool:
    try:
        datetime.fromisoformat(str(value)[:10])
        return True
    except ValueError:
        return False


def evaluate(primary: Mapping[str, Any] | None, candidate: Mapping[str, Any] | None,
             policy: Mapping[str, Any]) -> dict[str, Any]:
    """Return accepted/blocked with explicit reasons. Never mutates input."""
    target = str(policy.get("target_date") or "")
    primary_reasons: list[str] = []
    reasons: list[str] = []
    if not _valid_date(target):
        return {"status": "blocked", "action": "blocked_invalid_target", "reasons": ["invalid_target_date"]}

    if primary and not _invalid_ohlc(primary) and primary.get("Close") is not None:
        return {"status": "primary_ok", "action": "no_fallback", "reasons": [], "candidate": None}

    if not primary or primary.get("Close") is None:
        primary_reasons.append("primary_missing_close")
    if primary and _invalid_ohlc(primary):
        primary_reasons.append("primary_invalid_ohlc")

    if candidate is None:
        return {"status": "blocked", "action": "blocked_no_candidate", "reasons": primary_reasons}

    provider = str(candidate.get("provider") or "")
    approved = set(policy.get("approved_providers") or [])
    if provider not in approved:
        reasons.append("provider_not_approved")
    if not policy.get("rights_verified"):
        reasons.append("rights_unverified")
    if str(candidate.get("date") or "")[:10] != target:
        reasons.append("date_mismatch")
    if candidate.get("Close") is None:
        reasons.append("candidate_missing_close")
    if _invalid_ohlc(candidate):
        reasons.append("candidate_invalid_ohlc")
    if not candidate.get("source_url"):
        reasons.append("missing_source_url")
    if not candidate.get("fetched_at"):
        reasons.append("missing_fetched_at")
    if not candidate.get("evidence_sha256"):
        reasons.append("missing_evidence_hash")
    if policy.get("panel_price_basis") != candidate.get("price_basis"):
        reasons.append("price_basis_mismatch")
    if policy.get("requires_adjusted_close") and candidate.get("Adj_Close") is None:
        reasons.append("missing_adjusted_close")
    ref = policy.get("reference_close")
    if ref is not None and candidate.get("Close") is not None and abs(float(ref) - float(candidate["Close"])) > 0.01:
        reasons.append("close_conflict")
    if candidate.get("duplicate_of_existing"):
        reasons.append("duplicate_existing_row")

    if reasons:
        return {"status": "blocked", "action": "blocked_candidate_rejected",
                "reasons": sorted(set(reasons)), "candidate": None}
    return {
        "status": "accepted",
        "action": "fallback",
        "reasons": [],
        "candidate": {
            "provider": provider,
            "date": target,
            "Close": float(candidate["Close"]),
            "price_basis": candidate["price_basis"],
            "source_url": candidate["source_url"],
            "fetched_at": candidate["fetched_at"],
            "evidence_sha256": candidate["evidence_sha256"],
        },
    }
