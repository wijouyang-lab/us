from tools.research.sec_daily_index import parse_sec_master_index


ROWS = """CIK|Company Name|Form Type|Date Filed|Filename
320193|Apple Inc.|8-K|2026-10-22|edgar/data/320193/0000320193-26-000001.txt
320193|Apple Inc.|4|2026-10-22|edgar/data/320193/0000320193-26-000002.txt
789019|Microsoft Corp.|10-Q|2026-10-23|edgar/data/789019/0000789019-26-000003.txt
320193|Apple Inc.|8-K|2026-09-30|edgar/data/320193/0000320193-26-000004.txt
320193|Apple Inc.|8-K|2026-10-22|edgar/data/320193/0000320193-26-000001.txt
"""


def test_master_index_filters_watchlist_form_and_date_and_deduplicates():
    result = parse_sec_master_index(
        ROWS,
        cik_tickers={"0000320193": "AAPL", "789019": "MSFT"},
        start_date="2026-10-01",
        end_date="2026-10-23",
    )
    assert len(result["events"]) == 2
    assert [event["ticker"] for event in result["events"]] == ["AAPL", "MSFT"]
    assert result["events"][0]["accession_number"] == "0000320193-26-000001"
    assert result["metadata"]["duplicate_count_removed"] == 1
    assert result["metadata"]["timestamp_verified_count"] == 0
    assert all(event["availability_status"] == "index_metadata_only" for event in result["events"])


def test_master_index_does_not_invent_publication_or_first_seen_time():
    result = parse_sec_master_index(
        ROWS,
        cik_tickers={"320193": "AAPL"},
        start_date="2026-10-22",
        end_date="2026-10-22",
    )
    event = result["events"][0]
    assert event["publication_timestamp_utc"] is None
    assert event["first_seen_at_utc"] is None
    assert result["metadata"]["historical_pit_eligible"] is False


def test_master_index_counts_malformed_rows_and_excludes_unknown_cik():
    payload = ROWS + (
        "bad|row\n"
        "999999|Unknown|8-K|2026-10-22|edgar/data/999999/0000999999-26-000001.txt\n"
        "320193|Apple Inc.|8-K|2026-10-22|edgar/data/320193/000032019326000001/aapl.htm\n"
    )
    result = parse_sec_master_index(
        payload,
        cik_tickers={"320193": "AAPL"},
        start_date="2026-10-01",
        end_date="2026-10-31",
    )
    assert result["metadata"]["malformed_row_count"] == 1
    assert len(result["events"]) == 1


def test_master_index_rejects_invalid_date_window_and_cik():
    import pytest

    with pytest.raises(ValueError, match="start_date"):
        parse_sec_master_index(ROWS, cik_tickers={"320193": "AAPL"}, start_date="bad", end_date="2026-10-31")
    with pytest.raises(ValueError, match="invalid CIK"):
        parse_sec_master_index(ROWS, cik_tickers={"abc": "AAPL"}, start_date="2026-10-01", end_date="2026-10-31")
