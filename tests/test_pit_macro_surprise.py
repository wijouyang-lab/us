from tools.research.pit_macro_surprise import macro_surprise


def release(**overrides):
    value = {
        "published_at_utc": "2026-10-15T12:30:00Z",
        "first_seen_at_utc": "2026-10-15T12:30:05Z",
        "actual_value": 3.1,
        "consensus_value": 3.0,
        "consensus_asof_utc": "2026-10-15T12:00:00Z",
    }
    value.update(overrides)
    return value


def test_computes_surprise_only_when_consensus_predates_actual_release():
    result = macro_surprise(release(), "2026-10-15T12:31:00Z")
    assert result["eligible"] is True
    assert abs(result["surprise"] - 0.1) < 1e-9
    assert result["reason"] == "eligible"


def test_rejects_consensus_timestamp_after_actual_release():
    result = macro_surprise(
        release(consensus_asof_utc="2026-10-15T12:31:00Z"),
        "2026-10-15T12:32:00Z",
    )
    assert result == {
        "eligible": False,
        "reason": "consensus_after_actual_release",
        "surprise": None,
    }


def test_rejects_release_not_yet_published_at_decision():
    result = macro_surprise(release(), "2026-10-15T12:29:59Z")
    assert result["eligible"] is False
    assert result["reason"] == "actual_release_after_decision"
    assert result["surprise"] is None


def test_rejects_missing_consensus_timestamp_or_non_numeric_values():
    assert macro_surprise(
        release(consensus_asof_utc=None), "2026-10-15T12:31:00Z"
    )["reason"] == "consensus_timestamp_missing"
    assert macro_surprise(
        release(actual_value="unknown"), "2026-10-15T12:31:00Z"
    )["reason"] == "actual_or_consensus_not_numeric"


def test_rejects_unavailable_event_even_if_timestamps_and_values_look_valid():
    result = macro_surprise(
        release(availability_status="fetch_error"),
        "2026-10-15T12:31:00Z",
    )
    assert result == {
        "eligible": False,
        "reason": "event_unavailable:fetch_error",
        "surprise": None,
    }



def test_rejects_revised_macro_vintage_not_yet_available_at_decision():
    result = macro_surprise(
        release(vintage_at_utc="2026-10-16T12:30:00Z"),
        "2026-10-15T12:31:00Z",
    )
    assert result == {
        "eligible": False,
        "reason": "vintage_after_decision",
        "surprise": None,
    }


def test_rejects_macro_vintage_observed_before_its_vintage_timestamp():
    result = macro_surprise(
        release(vintage_at_utc="2026-10-15T12:30:10Z"),
        "2026-10-15T12:31:00Z",
    )
    assert result == {
        "eligible": False,
        "reason": "vintage_after_first_seen",
        "surprise": None,
    }


def test_rejects_invalid_macro_vintage_timestamp():
    result = macro_surprise(
        release(vintage_at_utc="2026-10-15 12:30:00"),
        "2026-10-15T12:31:00Z",
    )
    assert result == {
        "eligible": False,
        "reason": "vintage_timestamp_invalid",
        "surprise": None,
    }
