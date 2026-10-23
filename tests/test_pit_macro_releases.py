from tools.research.pit_macro_releases import normalize_macro_release


def test_macro_release_keeps_observation_period_separate_from_publication_time():
    record = normalize_macro_release(
        {
            "series_id": "CPIAUCSL",
            "observation_period": "2026-09",
            "actual_release_at_utc": "2026-10-13T12:30:00Z",
            "scheduled_release_at_utc": "2026-10-13T12:30:00Z",
            "value": 326.1,
            "units": "index",
            "consensus_value": 326.0,
            "consensus_asof_utc": "2026-10-13T12:00:00Z",
            "vintage_at_utc": "2026-10-13T12:30:00Z",
        },
        first_seen_at_utc="2026-10-13T12:30:05Z",
        source="bls",
    )
    assert record["event_type"] == "macro_release"
    assert record["published_at_utc"] == "2026-10-13T12:30:00Z"
    assert record["observation_period"] == "2026-09"
    assert record["value"] == 326.1
    assert record["consensus_value"] == 326.0
    assert record["availability_status"] == "available"


def test_scheduled_time_is_not_used_as_actual_publication_time():
    record = normalize_macro_release(
        {
            "series_id": "GDP",
            "observation_period": "2026-Q3",
            "scheduled_release_at_utc": "2026-10-29T12:30:00Z",
            "value": 3.2,
        },
        first_seen_at_utc="2026-10-29T12:31:00Z",
        source="bea",
    )
    assert record["published_at_utc"] is None
    assert record["availability_status"] == "timestamp_missing"
    assert record["scheduled_release_at_utc"] == "2026-10-29T12:30:00Z"


def test_macro_release_requires_series_and_observation_period():
    import pytest

    with pytest.raises(ValueError):
        normalize_macro_release(
            {"observation_period": "2026-09"},
            first_seen_at_utc="2026-10-13T12:30:05Z",
            source="bls",
        )
