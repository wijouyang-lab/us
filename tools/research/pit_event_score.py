"""Conservative point-in-time event score from explicitly annotated labels.

This module never infers direction from headlines. Each event must carry a
validated direction_score in [-1, 1] and impact_score in [0, 1], plus explicit
source/timestamp eligibility. Missing labels or coverage remain missing rather
than becoming neutral zero. Research-only: no production integration.
"""
from __future__ import annotations

from datetime import timedelta
import math
from typing import Any, Iterable, Mapping

from tools.research.pit_event_eligibility import event_eligibility


def score_events_for_ticker(
    events: Iterable[Mapping[str, Any]],
    *,
    ticker: str,
    decision_at: str,
    family_weights: Mapping[str, float],
    sector: str | None = None,
    max_age_by_type: Mapping[str, timedelta] | None = None,
) -> dict[str, Any]:
    """Compute a weighted average score using only eligible, explicitly labeled events.

    Relevance requires an explicit ticker match, explicit sector match, or
    market_scope='market'. direction_score must be a separately validated
    annotation (for example, a reviewed label); this function does not perform
    sentiment analysis or decide whether an event is bullish/bearish.
    """
    symbol = str(ticker or "").strip().upper().replace("$", "")
    sector_value = str(sector or "").strip().lower()
    if not symbol:
        raise ValueError("ticker is required")
    if not family_weights:
        raise ValueError("family_weights must not be empty")
    for family, weight in family_weights.items():
        if not math.isfinite(float(weight)):
            raise ValueError(f"non-finite weight for event family {family}")

    eligible_rows: list[dict[str, Any]] = []
    rejection_counts: dict[str, int] = {}
    relevant_count = 0
    unlabelled_count = 0
    for raw in events:
        event = dict(raw)
        family = str(event.get("event_type") or "unknown")
        event_tickers = {
            str(value).strip().upper().replace("$", "")
            for value in (event.get("tickers") or [])
        }
        event_sectors = {
            str(value).strip().lower()
            for value in (event.get("sectors") or [])
        }
        relevant = (
            symbol in event_tickers
            or (bool(sector_value) and sector_value in event_sectors)
            or str(event.get("market_scope") or "").strip().lower() == "market"
        )
        if not relevant:
            continue
        relevant_count += 1
        if str(event.get("availability_status") or "") != "available":
            reason = "coverage_unavailable"
            rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
            continue
        weight = float(family_weights.get(family, 0.0))
        if weight == 0:
            rejection_counts["family_unweighted"] = rejection_counts.get("family_unweighted", 0) + 1
            continue
        try:
            direction = float(event.get("direction_score"))
            impact = float(event.get("impact_score"))
        except (TypeError, ValueError):
            unlabelled_count += 1
            rejection_counts["missing_or_invalid_label"] = rejection_counts.get("missing_or_invalid_label", 0) + 1
            continue
        if not math.isfinite(direction) or not -1.0 <= direction <= 1.0:
            unlabelled_count += 1
            rejection_counts["missing_or_invalid_label"] = rejection_counts.get("missing_or_invalid_label", 0) + 1
            continue
        if not math.isfinite(impact) or not 0.0 <= impact <= 1.0:
            unlabelled_count += 1
            rejection_counts["missing_or_invalid_label"] = rejection_counts.get("missing_or_invalid_label", 0) + 1
            continue
        ok, reason = event_eligibility(
            event,
            decision_at,
            max_age=(max_age_by_type or {}).get(family),
        )
        if not ok:
            rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
            continue
        event_id = str(event.get("event_version_id") or event.get("event_id") or "")
        if not event_id:
            rejection_counts["missing_event_identity"] = rejection_counts.get("missing_event_identity", 0) + 1
            continue
        eligible_rows.append({
            "event_id": event_id,
            "event_type": family,
            "weighted_score": weight * direction * impact,
            "absolute_weight": abs(weight) * impact,
        })

    # One event version must not influence the score more than once.
    deduped: dict[str, dict[str, Any]] = {}
    for row in eligible_rows:
        deduped[row["event_id"]] = row
    rows = list(deduped.values())
    denominator = sum(row["absolute_weight"] for row in rows)
    score = (
        sum(row["weighted_score"] for row in rows) / denominator
        if rows and denominator > 0 else None
    )
    return {
        "ticker": symbol,
        "decision_at_utc": decision_at,
        "event_score": round(float(score), 8) if score is not None else None,
        "coverage_status": "available" if score is not None else "missing",
        "relevant_event_count": relevant_count,
        "eligible_labeled_event_count": len(rows),
        "unlabelled_event_count": unlabelled_count,
        "eligible_event_ids": sorted(row["event_id"] for row in rows),
        "rejection_reason_counts": dict(sorted(rejection_counts.items())),
        "score_semantics": "weighted mean of explicitly supplied direction_score * impact_score",
        "research_only": True,
        "production_signal_generated": False,
    }
