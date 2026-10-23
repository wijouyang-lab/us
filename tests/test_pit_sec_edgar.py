from tools.research.pit_sec_edgar import parse_sec_submissions


def test_parse_sec_recent_filings_uses_acceptance_time_and_stable_rows():
    payload = {
        "name": "Example Corp",
        "filings": {
            "recent": {
                "accessionNumber": ["0000123456-26-000001", "0000123456-26-000002"],
                "form": ["10-Q", "8-K"],
                "filingDate": ["2026-10-22", "2026-10-22"],
                "acceptanceDateTime": ["2026-10-22T15:30:00Z", "2026-10-22T16:30:00Z"],
                "primaryDocument": ["quarter.htm", "current.htm"],
                "items": ["", "2.02, 9.01"],
            }
        },
    }
    records = parse_sec_submissions(
        payload, first_seen_at_utc="2026-10-22T17:00:00Z", ticker="EXM",
    )
    assert len(records) == 2
    assert records[0]["published_at_utc"] == "2026-10-22T15:30:00Z"
    assert records[0]["event_type"] == "earnings"
    assert records[1]["event_type"] == "earnings"
    assert records[0]["tickers"] == ["EXM"]


def test_parse_sec_does_not_treat_filing_date_as_publication_time():
    payload = {
        "name": "Example Corp",
        "filings": {
            "recent": {
                "accessionNumber": ["0000123456-26-000003"],
                "form": ["8-K"],
                "filingDate": ["2026-10-22"],
                "primaryDocument": ["current.htm"],
                "items": ["5.02"],
            }
        },
    }
    record = parse_sec_submissions(
        payload, first_seen_at_utc="2026-10-22T17:00:00Z", ticker="EXM",
    )[0]
    assert record["published_at_utc"] is None
    assert record["availability_status"] == "timestamp_missing"
    assert record["event_type"] == "company_news"


def test_parse_sec_handles_missing_or_malformed_payload_safely():
    assert parse_sec_submissions({}, first_seen_at_utc="2026-10-22T17:00:00Z") == []
    assert parse_sec_submissions(
        {"filings": {"recent": {"form": ["10-Q"], "accessionNumber": []}}},
        first_seen_at_utc="2026-10-22T17:00:00Z",
    ) == []
