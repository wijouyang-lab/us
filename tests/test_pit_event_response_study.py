import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from tools.research.pit_event_response_study import (
    _load_price_bars,
    parse_max_age_days,
    run_event_response_study,
)
from tools.research.pit_event_records import normalize_event


def event(source_id, first_seen, published, *, kind="macro_release", tickers=None, status="available", payload=None):
    row = normalize_event(
        source="study_test",
        source_event_id=source_id,
        event_type=kind,
        published_at_utc=published,
        first_seen_at_utc=first_seen,
        tickers=tickers or [],
        raw_payload=payload or {"title": source_id},
    )
    if status != "available":
        row["availability_status"] = status
    return row


def price_bars():
    days = [
        ("2026-10-23", 100.0, 102.0),
        ("2026-10-26", 103.0, 104.0),
        ("2026-10-27", 105.0, 106.0),
        ("2026-10-28", 107.0, 108.0),
        ("2026-10-29", 109.0, 110.0),
    ]
    spy = [{"date": date.fromisoformat(d), "open": op, "close": close} for d, op, close in days]
    exm = [{"date": date.fromisoformat(d), "open": 50.0+i, "close": 50.5+i} for i, (d, _, _) in enumerate(days)]
    return {"SPY": spy, "EXM": exm}


def test_premarket_event_enters_same_day_open_and_reports_forward_returns():
    row = event("cpi-1", "2026-10-23T12:00:00Z", "2026-10-23T11:30:00Z")
    report = run_event_response_study(
        [row], price_bars(), study_end_date="2026-10-29",
        horizons=[1, 3], max_age_by_type={"macro_release": timedelta(days=1)},
        round_trip_cost_bps=5.0,
    )
    observation = report["observations"][0]
    assert observation["ticker"] == "SPY"
    assert observation["entry_date"] == "2026-10-23"
    assert observation["gross_return_1s"] == pytest.approx(0.02)
    assert observation["net_return_1s"] == pytest.approx(0.0195)
    assert observation["gross_return_3s"] == pytest.approx(0.06)
    assert report["aggregates_by_event_type"][0]["observation_count"] == 1
    assert report["trading_signal_generated"] is False


def test_event_first_seen_after_open_enters_next_available_session():
    row = event("fed-1", "2026-10-23T14:00:00Z", "2026-10-23T13:45:00Z", kind="policy")
    report = run_event_response_study(
        [row], price_bars(), study_end_date="2026-10-29", horizons=[1],
    )
    assert report["observations"][0]["entry_date"] == "2026-10-26"
    assert report["observations"][0]["entry_open"] == 103.0


def test_missing_mapping_timestamps_and_unavailable_events_are_skipped():
    no_mapping = event("story-1", "2026-10-23T12:00:00Z", "2026-10-23T11:00:00Z", kind="company_news")
    missing_time = event("cpi-2", "2026-10-23T12:00:00Z", None)
    failed = event("cpi-3", "2026-10-23T12:00:00Z", "2026-10-23T11:00:00Z", status="fetch_error")
    report = run_event_response_study(
        [no_mapping, missing_time, failed], price_bars(),
        study_end_date="2026-10-29", horizons=[1],
    )
    assert report["observation_count"] == 0
    assert report["skip_reason_counts"]["availability_mapping_missing"] == 1
    assert report["skip_reason_counts"]["availability_timestamp_missing"] == 1
    assert report["skip_reason_counts"]["availability_fetch_error"] == 1


def test_only_earliest_observed_version_used_not_later_revision():
    initial = event(
        "story-update", "2026-10-22T12:00:00Z", "2026-10-22T11:00:00Z",
        kind="company_news", tickers=["EXM"], payload={"title": "first"},
    )
    revision = event(
        "story-update", "2026-10-23T12:00:00Z", "2026-10-22T11:00:00Z",
        kind="company_news", tickers=["EXM"], payload={"title": "correction"},
    )
    report = run_event_response_study(
        [initial, revision], price_bars(), study_end_date="2026-10-29", horizons=[1],
    )
    assert len(report["observations"]) == 1
    assert report["observations"][0]["first_seen_at_utc"] == "2026-10-22T12:00:00Z"
    assert report["skip_reason_counts"]["later_revision_excluded"] == 1


def test_first_version_with_missing_timestamp_blocks_later_correction():
    first = event("stale-story", "2026-10-22T12:00:00Z", None, kind="company_news", tickers=["EXM"])
    later = event(
        "stale-story", "2026-10-23T12:00:00Z", "2026-10-23T11:00:00Z",
        kind="company_news", tickers=["EXM"], payload={"title": "corrected"},
    )
    report = run_event_response_study(
        [first, later], price_bars(), study_end_date="2026-10-29", horizons=[1],
    )
    assert report["observation_count"] == 0
    assert report["skip_reason_counts"]["availability_timestamp_missing"] == 1


def test_horizon_without_enough_future_bars_is_reported_not_imputed():
    row = event("cpi-end", "2026-10-29T12:00:00Z", "2026-10-29T11:30:00Z")
    report = run_event_response_study(
        [row], price_bars(), study_end_date="2026-10-29", horizons=[1, 5],
    )
    assert report["observations"][0]["gross_return_1s"] is not None
    assert report["observations"][0]["gross_return_5s"] is None
    assert report["skip_reason_counts"]["insufficient_price_horizon_5s"] == 1


def test_price_csv_rejects_duplicate_ticker_sessions(tmp_path):
    path = tmp_path / "prices.csv"
    path.write_text("Date,Ticker,Open,Close\n2026-10-23,SPY,100,101\n2026-10-23,SPY,101,102\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate ticker/date"):
        _load_price_bars(path, date(2026, 10, 29))


def test_freshness_config_rejects_bad_values():
    assert parse_max_age_days('{"macro_release":1}') == {"macro_release": timedelta(days=1)}
    with pytest.raises(ValueError, match="finite"):
        parse_max_age_days('{"macro_release":1e999}')
    with pytest.raises(ValueError, match="finite"):
        parse_max_age_days('{"macro_release":-1}')
