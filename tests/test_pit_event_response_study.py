import json
from hashlib import sha256
from datetime import date, timedelta
from pathlib import Path

import pytest

from tools.research.pit_event_response_study import (
    _load_price_bars,
    parse_max_age_days,
    run_event_response_study,
)


def event(source_id, first_seen, published, *, kind="macro_release", tickers=None, status="available", payload=None):
    normalized_tickers = sorted({
        str(value).strip().upper().replace("$", "")
        for value in (tickers or [])
        if str(value).strip()
    })
    raw_payload = payload or {"title": source_id}
    row = {
        "event_id": sha256(f"study_test|{source_id}".encode("utf-8")).hexdigest(),
        "source": "study_test",
        "source_event_id": source_id,
        "event_type": kind,
        "published_at_utc": published,
        "first_seen_at_utc": first_seen,
        "updated_at_utc": None,
        "update_first_seen_at_utc": None,
        "headline": str(raw_payload.get("title") or source_id),
        "tickers": normalized_tickers,
        "sectors": [],
        "source_quality": "official",
        "content_hash": sha256(json.dumps(raw_payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest(),
    }
    if published is None or not first_seen:
        availability = "timestamp_missing"
    elif not normalized_tickers and kind in {"company_news", "earnings"}:
        availability = "mapping_missing"
    else:
        availability = "available"
    row["availability_status"] = status if status != "available" else availability
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
    aapl = [{"date": date.fromisoformat(d), "open": 200.0+i, "close": 201.0+i} for i, (d, _, _) in enumerate(days)]
    return {"SPY": spy, "EXM": exm, "AAPL": aapl}


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


def test_price_loader_derives_adjusted_open_from_same_session_adjustment_factor(tmp_path):
    path = tmp_path / "prices.csv"
    path.write_text(
        "Date,Ticker,Open,Close,Adj Close\n"
        "2026-10-23,SPY,100,110,105\n"
        "2026-10-26,SPY,105,112,107\n",
        encoding="utf-8",
    )
    price_map, _, quality = _load_price_bars(path, date(2026, 10, 26))
    assert quality["selected_price_basis"] == "adjusted_ohlc_derived_open"
    assert quality["usable_price_row_count"] == 2
    assert quality["adjusted_open_derivation"] == "raw_open * adj_close / raw_close"
    assert price_map["SPY"][0]["open"] == pytest.approx(100 * 105 / 110)
    assert price_map["SPY"][0]["close"] == 105


def test_price_loader_prefers_explicit_adjusted_open_and_close(tmp_path):
    path = tmp_path / "adjusted.csv"
    path.write_text(
        "Date,Ticker,Open,Close,Adj Open,Adj Close\n"
        "2026-10-23,SPY,,,95,105\n",
        encoding="utf-8",
    )
    price_map, _, quality = _load_price_bars(path, date(2026, 10, 23))
    assert quality["selected_price_basis"] == "adjusted_ohlc"
    assert price_map["SPY"][0]["open"] == 95
    assert price_map["SPY"][0]["close"] == 105


def test_price_loader_does_not_fallback_to_raw_on_missing_adjusted_values(tmp_path):
    path = tmp_path / "missing_adj.csv"
    path.write_text(
        "Date,Ticker,Open,Close,Adj Close\n"
        "2026-10-23,SPY,100,110,\n"
        "2026-10-26,SPY,105,112,107\n",
        encoding="utf-8",
    )
    price_map, _, quality = _load_price_bars(path, date(2026, 10, 26))
    assert quality["selected_price_basis"] == "adjusted_ohlc_derived_open"
    assert len(price_map["SPY"]) == 1
    assert quality["skipped_rows_missing_or_invalid_selected_basis"] == 1


def test_explicit_adjusted_basis_requires_adjustment_fields(tmp_path):
    path = tmp_path / "raw.csv"
    path.write_text(
        "Date,Ticker,Open,Close\n"
        "2026-10-23,SPY,100,110\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="adjusted price basis requires"):
        _load_price_bars(path, date(2026, 10, 23), price_basis="adjusted")


def test_unverified_ticker_scoped_aggregator_news_is_not_matched_to_stock_returns():
    yahoo_event = event(
        "yahoo-story-unverified",
        "2026-10-26T15:00:00Z",
        "2026-10-26T14:30:00Z",
        kind="company_news",
        tickers=["AAPL"],
        payload={"title": "A headline surfaced by the AAPL query"},
    )
    yahoo_event["source"] = "yahoo_finance_rss"
    yahoo_event["source_quality"] = "aggregator"
    yahoo_event["ticker_mapping_method"] = "per_ticker_yahoo_rss_query"
    yahoo_event["ticker_mapping_status"] = "unverified_query_scope"
    yahoo_event["ticker_mapping_confidence"] = "unverified"

    report = run_event_response_study(
        [yahoo_event],
        price_bars(),
        study_end_date="2026-10-30",
        horizons=[1],
    )

    assert report["observation_count"] == 0
    assert report["skip_reason_counts"]["company_event_ticker_mapping_unverified"] == 1


def test_verified_aggregator_company_mapping_can_be_studied():
    from tools.research.pit_event_archive import event_version_id

    yahoo_event = event(
        "yahoo-story-reviewed",
        "2026-10-26T15:00:00Z",
        "2026-10-26T14:30:00Z",
        kind="company_news",
        tickers=["AAPL"],
        payload={"title": "A headline reviewed as about AAPL"},
    )
    yahoo_event["source"] = "yahoo_finance_rss"
    yahoo_event["source_quality"] = "aggregator"
    yahoo_event["ticker_mapping_method"] = "per_ticker_yahoo_rss_query"
    yahoo_event["ticker_mapping_status"] = "unverified_query_scope"
    yahoo_event["ticker_mapping_confidence"] = "unverified"
    yahoo_event["event_version_id"] = event_version_id(yahoo_event)
    yahoo_event.update({
        "ticker_mapping_review_status": "human_reviewed",
        "ticker_mapping_reviewed_tickers": ["AAPL"],
        "ticker_mapping_reviewed_at_utc": "2026-10-26T15:30:00Z",
        "ticker_mapping_reviewer_id": "mapping-reviewer-1",
        "ticker_mapping_rationale": "The reviewed headline is explicitly about Apple.",
        "ticker_mapping_schema_version": "1.0",
    })
    report = run_event_response_study(
        [yahoo_event], price_bars(), study_end_date="2026-10-30", horizons=[1],
    )
    assert report["observation_count"] == 1
    observation = report["observations"][0]
    assert observation["ticker_mapping_status"] == "human_reviewed"
    assert observation["ticker_mapping_reviewer_id"] == "mapping-reviewer-1"
    assert observation["ticker_mapping_review_was_available_by_entry"] is True


def test_observation_csv_preserves_reviewed_ticker_mapping_provenance(tmp_path):
    from csv import DictReader
    from tools.research.pit_event_response_study import write_observations_csv
    from tools.research.pit_event_archive import event_version_id

    yahoo_event = event(
        "yahoo-story-reviewed-csv",
        "2026-10-26T15:00:00Z",
        "2026-10-26T14:30:00Z",
        kind="company_news",
        tickers=["AAPL"],
        payload={"title": "A headline reviewed as about AAPL"},
    )
    yahoo_event["source"] = "yahoo_finance_rss"
    yahoo_event["source_quality"] = "aggregator"
    yahoo_event["ticker_mapping_method"] = "per_ticker_yahoo_rss_query"
    yahoo_event["ticker_mapping_status"] = "unverified_query_scope"
    yahoo_event["ticker_mapping_confidence"] = "unverified"
    yahoo_event["event_version_id"] = event_version_id(yahoo_event)
    yahoo_event.update({
        "ticker_mapping_review_status": "human_reviewed",
        "ticker_mapping_reviewed_tickers": ["AAPL"],
        "ticker_mapping_reviewed_at_utc": "2026-10-26T15:30:00Z",
        "ticker_mapping_reviewer_id": "mapping-reviewer-1",
        "ticker_mapping_rationale": "The reviewed headline is explicitly about Apple.",
        "ticker_mapping_schema_version": "1.0",
    })
    report = run_event_response_study(
        [yahoo_event], price_bars(), study_end_date="2026-10-30", horizons=[1],
    )
    output = tmp_path / "observations.csv"
    write_observations_csv(output, report)
    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(DictReader(stream))
    assert len(rows) == 1
    assert rows[0]["ticker_mapping_status"] == "human_reviewed"
    assert rows[0]["ticker_mapping_confidence"] == "unverified"
    assert rows[0]["ticker_mapping_method"] == "per_ticker_yahoo_rss_query"
    assert rows[0]["ticker_mapping_reviewer_id"] == "mapping-reviewer-1"
    assert rows[0]["ticker_mapping_review_was_available_by_entry"] == "True"
    assert rows[0]["ticker_mapping_reviewed_at_utc"] == "2026-10-26T15:30:00Z"


def test_publication_to_first_seen_delay_gate_excludes_stale_rss_backfill():
    first_seen = "2026-10-23T16:57:17Z"
    stale = event("old-rss-backfill", first_seen, "2026-09-24T18:30:00Z")
    fresh = event("fresh-release", first_seen, "2026-10-23T16:00:00Z")
    report = run_event_response_study(
        [stale, fresh],
        price_bars(),
        study_end_date="2026-10-29",
        horizons=[1],
        max_age_by_type={"macro_release": timedelta(days=2)},
    )
    assert report["observation_count"] == 1
    assert report["observations"][0]["event_id"] == fresh["event_id"]
    assert report["skip_reason_counts"]["stale_event_at_first_observation"] == 1
    assert report["max_publication_to_first_seen_delay_days_by_type"] == {"macro_release": 2.0}
    assert "publication-to-first-seen delay" in report["methodology"]["freshness_rule"]


def test_aggregates_expose_duplicate_events_sharing_same_ticker_entry_session():
    first_seen = "2026-10-23T12:00:00Z"
    one = event("same-session-one", first_seen, "2026-10-23T11:30:00Z")
    two = event("same-session-two", first_seen, "2026-10-23T11:45:00Z")
    report = run_event_response_study(
        [one, two], price_bars(), study_end_date="2026-10-29", horizons=[1],
    )
    assert report["observation_count"] == 2
    aggregate = report["aggregates_by_event_type"][0]
    assert aggregate["observation_count"] == 2
    assert aggregate["distinct_event_count"] == 2
    assert aggregate["distinct_ticker_entry_sessions"] == 1
    assert aggregate["session_deduplicated_observation_count"] == 1
    assert aggregate["session_deduplicated_mean_gross_return"] == pytest.approx(
        report["observations"][0]["gross_return_1s"]
    )
