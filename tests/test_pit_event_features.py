from datetime import timedelta

from tools.research.pit_event_features import build_event_features


DECISION = "2026-10-23T14:00:00Z"


def event(**overrides):
    row = {
        "event_id": "event-1",
        "event_type": "company_news",
        "published_at_utc": "2026-10-23T13:00:00Z",
        "first_seen_at_utc": "2026-10-23T13:01:00Z",
        "availability_status": "available",
        "tickers": ["AAPL"],
        "sectors": [],
    }
    row.update(overrides)
    return row


def test_features_include_only_explicitly_mapped_and_eligible_events():
    rows = [
        event(),
        event(event_id="future", published_at_utc="2026-10-23T14:01:00Z"),
        event(event_id="other-ticker", tickers=["MSFT"]),
    ]
    result = build_event_features(rows, ticker="aapl", decision_at=DECISION)
    family = result["event_families"]["company_news"]
    assert family["eligible_event_count"] == 1
    assert family["eligible_event_ids"] == ["event-1"]
    assert result["coverage_status"] == "available"


def test_official_macro_events_can_flow_into_ticker_features_as_market_context():
    from tools.research.official_event_rss_collector import parse_official_feed

    feed = """<rss><channel><item>
    <title>CPI release</title>
    <link>https://www.bls.gov/news.release/cpi.htm</link>
    <guid>cpi-market-context-1</guid>
    <pubDate>Fri, 23 Oct 2026 08:30:00 -0400</pubDate>
    </item></channel></rss>"""
    parsed = parse_official_feed(
        feed,
        feed_key="bls_cpi",
        first_seen_at_utc="2026-10-23T12:31:00Z",
    )
    result = build_event_features(
        parsed["events"],
        ticker="AAPL",
        decision_at="2026-10-23T13:00:00Z",
    )
    family = result["event_families"]["macro_release"]
    assert family["eligible_event_count"] == 1
    assert family["eligible_event_ids"] == [parsed["events"][0]["event_id"]]
    assert result["coverage_status"] == "available"


def test_unmapped_market_events_do_not_leak_to_every_ticker():
    result = build_event_features(
        [event(event_type="macro_release", tickers=[], sectors=[])],
        ticker="AAPL",
        decision_at=DECISION,
    )
    assert result["event_family_count"] == 0
    assert result["coverage_status"] == "missing"


def test_explicit_market_scope_can_supply_market_wide_context():
    result = build_event_features(
        [event(event_type="macro_release", tickers=[], market_scope="market")],
        ticker="AAPL",
        decision_at=DECISION,
    )
    assert result["event_families"]["macro_release"]["eligible_event_count"] == 1


def test_missing_event_data_is_not_reported_as_zero_neutral_feature():
    result = build_event_features(
        [event(event_id="missing", availability_status="timestamp_missing")],
        ticker="AAPL",
        decision_at=DECISION,
    )
    family = result["event_families"]["company_news"]
    assert family["coverage_status"] == "missing"
    assert family["eligible_event_count"] == 0
    assert family["missing_event_count"] == 1
    assert result["coverage_status"] == "missing"


def test_stale_events_are_excluded_and_feature_time_is_decision_time():
    result = build_event_features(
        [event(published_at_utc="2026-10-20T13:00:00Z")],
        ticker="AAPL",
        decision_at=DECISION,
        max_age_by_type={"company_news": timedelta(days=1)},
    )
    assert result["event_families"]["company_news"]["eligible_event_count"] == 0
    assert result["event_families"]["company_news"]["coverage_status"] == "missing"
    assert result["feature_asof_utc"] == DECISION
    assert result["rejection_reason_counts"] == {"stale_event": 1}
