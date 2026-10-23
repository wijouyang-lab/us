from __future__ import annotations

from tools.research.pit_event_score import score_events_for_ticker


DECISION = "2026-01-10T15:00:00Z"


def event(event_id, event_type, direction, impact, published="2026-01-10T13:00:00Z"):
    return {
        "event_id": event_id,
        "event_type": event_type,
        "tickers": ["ABC"],
        "availability_status": "available",
        "published_at_utc": published,
        "first_seen_at_utc": "2026-01-10T13:01:00Z",
        "direction_score": direction,
        "impact_score": impact,
    }


def test_score_uses_only_labeled_point_in_time_events_and_is_bounded():
    rows = [
        event("earn-1", "earnings", 1, 1),
        event("news-1", "news", -1, 0.5),
        event("future", "news", 1, 1, published="2026-01-10T16:00:00Z"),
        event("unlabelled", "news", None, None),
    ]
    result = score_events_for_ticker(
        rows,
        ticker="abc",
        decision_at=DECISION,
        family_weights={"earnings": 2, "news": 1},
    )
    assert result["event_score"] == 0.6
    assert result["coverage_status"] == "available"
    assert result["eligible_labeled_event_count"] == 2
    assert result["unlabelled_event_count"] == 1
    assert result["eligible_event_ids"] == ["earn-1", "news-1"]
    assert result["production_signal_generated"] is False


def test_score_preserves_missingness_when_no_eligible_labeled_events():
    result = score_events_for_ticker(
        [event("bad", "earnings", None, None)],
        ticker="ABC",
        decision_at=DECISION,
        family_weights={"earnings": 1},
    )
    assert result["event_score"] is None
    assert result["coverage_status"] == "missing"
