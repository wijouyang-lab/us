from datetime import datetime, timedelta, timezone

import pytest

from tools.research.pit_event_eligibility import event_eligibility


UTC = timezone.utc
DECISION = datetime(2026, 10, 22, 14, 0, tzinfo=UTC)


def event(**overrides):
    value = {
        "published_at_utc": "2026-10-22T13:00:00Z",
        "first_seen_at_utc": "2026-10-22T13:01:00+00:00",
        "research_ready_at_utc": "2026-10-22T13:01:00+00:00",
        "parse_status": "exact",
        "source_evidence": "official_fed_page",
        "published_at_evidence": "official_release_time_in_page",
        "decision_evidence": "strategy_log",
        "is_simulated": False,
        "is_historical_backfill": False,
        "observation_kind": "live_forward_observation",
    }
    value.update(overrides)
    return value


def test_accepts_event_observed_before_decision():
    assert event_eligibility(event(), DECISION) == (True, "eligible")


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"published_at_utc": "2026-10-22T14:00:01Z"}, "published_after_decision"),
        ({"first_seen_at_utc": "2026-10-22T14:00:01Z"}, "first_seen_after_decision"),
        ({"published_at_utc": None}, "missing_or_invalid_required_timestamp"),
        ({"first_seen_at_utc": "2026-10-22 13:01:00"}, "missing_or_invalid_required_timestamp"),
        ({"published_at_utc": "not-a-date"}, "missing_or_invalid_required_timestamp"),
        ({"first_seen_at_utc": "2026-10-22T12:59:00Z"}, "first_seen_before_publication"),
    ],
)
def test_rejects_future_or_unverifiable_event_timestamps(overrides, reason):
    eligible, actual_reason = event_eligibility(event(**overrides), DECISION)
    assert not eligible
    assert actual_reason == reason


def test_rejects_unseen_later_revision():
    revised = event(
        updated_at_utc="2026-10-22T13:55:00Z",
        update_first_seen_at_utc="2026-10-22T14:00:01Z",
    )
    assert event_eligibility(revised, DECISION) == (False, "update_after_decision")


def test_rejects_update_without_verifiable_observation_time():
    revised = event(updated_at_utc="2026-10-22T13:55:00Z")
    assert event_eligibility(revised, DECISION) == (False, "unverifiable_update_timestamp")


def test_rejects_update_observed_before_source_update_timestamp():
    revised = event(
        updated_at_utc="2026-10-22T13:55:00Z",
        update_first_seen_at_utc="2026-10-22T13:54:00Z",
    )
    assert event_eligibility(revised, DECISION) == (False, "update_seen_before_update")


def test_freshness_uses_publication_time_and_boundary_is_inclusive():
    fresh = event(published_at_utc="2026-10-21T14:00:00Z", first_seen_at_utc="2026-10-21T14:01:00Z")
    assert event_eligibility(fresh, DECISION, max_age=timedelta(days=1)) == (True, "eligible")
    stale = event(published_at_utc="2026-10-21T13:59:59Z", first_seen_at_utc="2026-10-21T14:01:00Z")
    assert event_eligibility(stale, DECISION, max_age=timedelta(days=1)) == (False, "stale_event")


def test_rejects_naive_decision_timestamp_and_negative_freshness():
    assert event_eligibility(event(), "2026-10-22T14:00:00") == (False, "invalid_decision_timestamp")
    with pytest.raises(ValueError, match="cannot be negative"):
        event_eligibility(event(), DECISION, max_age=timedelta(seconds=-1))
def test_strict_admission_rejects_missing_evidence():
    assert event_eligibility(event(source_evidence=None), DECISION) == (False, "pit_admission:source_evidence_not_verified")
    assert event_eligibility(event(decision_evidence=None), DECISION) == (False, "pit_admission:decision_evidence_missing")
    assert event_eligibility(event(is_simulated=True), DECISION) == (False, "pit_admission:simulated_record")
