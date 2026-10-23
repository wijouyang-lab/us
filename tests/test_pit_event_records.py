from tools.research.pit_event_records import normalize_event, normalize_sec_filing


def test_normalize_event_is_stable_and_normalizes_tickers_and_timestamps():
    kwargs = dict(
        source=" SEC_EDGAR ",
        source_event_id="0001",
        event_type="company_news",
        published_at_utc="2026-10-22T13:00:00-04:00",
        first_seen_at_utc="2026-10-22T17:01:00Z",
        headline="  Company   announces   results ",
        tickers=["aapl", "$AAPL", " msft "],
        raw_payload={"b": 2, "a": 1},
    )
    first = normalize_event(**kwargs)
    second = normalize_event(**kwargs)
    assert first == second
    assert first["source"] == "sec_edgar"
    assert first["published_at_utc"] == "2026-10-22T17:00:00Z"
    assert first["tickers"] == ["AAPL", "MSFT"]
    assert first["headline"] == "Company announces results"
    assert first["availability_status"] == "available"


def test_missing_timestamps_and_company_mapping_are_not_marked_available():
    missing_time = normalize_event(
        source="rss", source_event_id="item-1", event_type="other",
        published_at_utc=None, first_seen_at_utc="2026-10-22T13:00:00Z",
    )
    missing_mapping = normalize_event(
        source="rss", source_event_id="item-2", event_type="company_news",
        published_at_utc="2026-10-22T12:00:00Z",
        first_seen_at_utc="2026-10-22T13:00:00Z",
    )
    assert missing_time["availability_status"] == "timestamp_missing"
    assert missing_mapping["availability_status"] == "mapping_missing"


def test_unknown_event_type_is_preserved_as_other_and_content_hash_changes():
    base = dict(
        source="rss", source_event_id="item-3", event_type="unreviewed_type",
        published_at_utc="2026-10-22T12:00:00Z",
        first_seen_at_utc="2026-10-22T13:00:00Z",
    )
    one = normalize_event(**base, raw_payload={"title": "A"})
    two = normalize_event(**base, raw_payload={"title": "B"})
    assert one["event_type"] == "other"
    assert one["event_id"] == two["event_id"]
    assert one["content_hash"] != two["content_hash"]


def test_sec_filing_does_not_assume_filing_date_is_publication_timestamp():
    filing = {
        "accessionNumber": "0000123456-26-000001",
        "form": "10-Q",
        "filingDate": "2026-10-22",
        "primaryDocument": "report.htm",
        "companyName": "Example Corp",
    }
    record = normalize_sec_filing(
        filing, first_seen_at_utc="2026-10-22T17:00:00Z", ticker="EXM",
    )
    assert record["event_type"] == "earnings"
    assert record["published_at_utc"] is None
    assert record["availability_status"] == "timestamp_missing"
    assert record["tickers"] == ["EXM"]


def test_sec_filing_uses_only_separately_verified_utc_timestamp():
    filing = {
        "accessionNumber": "0000123456-26-000002",
        "form": "8-K",
        "acceptanceDateTimeUtc": "2026-10-22T15:30:00Z",
        "verifiedPublishedAtUtc": "2026-10-22T15:30:00Z",
        "primaryDocument": "current.htm",
        "companyName": "Example Corp",
    }
    record = normalize_sec_filing(
        filing, first_seen_at_utc="2026-10-22T15:31:00Z", ticker="EXM",
    )
    assert record["published_at_utc"] == "2026-10-22T15:30:00Z"
    assert record["availability_status"] == "available"
    assert record["event_type"] == "company_news"
