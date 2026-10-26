from datetime import datetime, timezone
from io import BytesIO
from urllib.error import HTTPError

import pytest

from tools.research.sec_master_index_capture import (
    build_master_index_url,
    fetch_master_index,
)


INDEX = b"""CIK|Company Name|Form Type|Date Filed|Filename
320193|Apple Inc.|8-K|2026-10-22|edgar/data/320193/000032019326000001/aapl-20261022.htm
789019|Microsoft Corp.|10-Q|2026-10-23|edgar/data/789019/000078901926000003/msft-20261023.htm
"""
NOW = datetime(2026, 10, 24, 11, 0, tzinfo=timezone.utc)


class Response(BytesIO):
    pass


def test_build_master_index_url_is_quarter_bounded():
    assert build_master_index_url("2026-10-01", "2026-10-24") == (
        "https://www.sec.gov/Archives/edgar/full-index/2026/QTR4/master.idx"
    )
    with pytest.raises(ValueError, match="single calendar quarter"):
        build_master_index_url("2026-09-30", "2026-10-01")


def test_fetch_master_index_captures_explicit_universe_and_pit_limits():
    seen = {}

    def opener(request, timeout):
        seen["url"] = request.full_url
        seen["ua"] = request.get_header("User-agent")
        return Response(INDEX)

    result = fetch_master_index(
        cik_tickers={"320193": "AAPL", "789019": "MSFT"},
        start_date="2026-10-01",
        end_date="2026-10-24",
        user_agent="research bot (contact: analyst@example.com)",
        opener=opener,
        now=lambda: NOW,
        sleep=lambda _: None,
    )
    assert seen["url"].endswith("/2026/QTR4/master.idx")
    assert "analyst@example.com" in seen["ua"]
    assert [e["ticker"] for e in result["events"]] == ["AAPL", "MSFT"]
    assert all(e["publication_timestamp_utc"] is None for e in result["events"])
    assert all(e["first_seen_at_utc"] == "2026-10-24T11:00:00Z" for e in result["events"])
    assert result["metadata"]["historical_pit_eligible"] is False
    assert result["metadata"]["timestamp_verified_count"] == 0


def test_fetch_master_index_rejects_missing_contact_and_bad_payload():
    with pytest.raises(ValueError, match="contact information"):
        fetch_master_index(
            cik_tickers={"320193": "AAPL"},
            start_date="2026-10-01",
            end_date="2026-10-24",
            user_agent="research bot",
            opener=lambda *args, **kwargs: Response(INDEX),
            sleep=lambda _: None,
        )
    with pytest.raises(ValueError, match="missing the expected header"):
        fetch_master_index(
            cik_tickers={"320193": "AAPL"},
            start_date="2026-10-01",
            end_date="2026-10-24",
            user_agent="research bot (contact: analyst@example.com)",
            opener=lambda *args, **kwargs: Response(b"access denied"),
            sleep=lambda _: None,
        )


def test_fetch_master_index_reports_http_errors_without_retrying():
    calls = []

    def opener(request, timeout):
        calls.append(request.full_url)
        raise HTTPError(request.full_url, 403, "Forbidden", {}, None)

    with pytest.raises(RuntimeError, match="HTTP 403"):
        fetch_master_index(
            cik_tickers={"320193": "AAPL"},
            start_date="2026-10-01",
            end_date="2026-10-24",
            user_agent="research bot (contact: analyst@example.com)",
            opener=opener,
            sleep=lambda _: None,
        )
    assert len(calls) == 1
