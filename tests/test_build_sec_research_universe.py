from datetime import datetime, timezone
import json

import pytest

from tools.research.build_sec_research_universe import (
    SEC_TICKERS_URL,
    build_sec_universe,
    fetch_sec_universe,
    load_requested_tickers,
)


def payload():
    return json.dumps({
        "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
        "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corporation"},
        "2": {"cik_str": 1067983, "ticker": "BRK.B", "title": "Berkshire Hathaway Inc."},
    })


def test_build_sec_universe_matches_requested_tickers_and_reports_unmatched():
    universe, metadata = build_sec_universe(
        ["AAPL", "BRK-B", "NOPE"],
        payload(),
        retrieved_at_utc="2026-10-23T17:00:00Z",
    )
    assert universe == [
        {"cik": "0000320193", "ticker": "AAPL"},
        {"cik": "0001067983", "ticker": "BRK-B"},
    ]
    assert metadata["matched_tickers"] == ["AAPL", "BRK-B"]
    assert metadata["unmatched_tickers"] == ["NOPE"]
    assert metadata["historical_membership_inferred"] is False


def test_build_sec_universe_rejects_bad_url_or_payload():
    with pytest.raises(ValueError, match="allowlist"):
        build_sec_universe(
            ["AAPL"], payload(), retrieved_at_utc="2026-10-23T17:00:00Z",
            source_url="https://example.com/tickers.json",
        )
    with pytest.raises(ValueError, match="invalid SEC company ticker JSON"):
        build_sec_universe(
            ["AAPL"], "<not-json>", retrieved_at_utc="2026-10-23T17:00:00Z",
        )
    with pytest.raises(ValueError, match="none of the requested tickers"):
        build_sec_universe(
            ["NOPE"], payload(), retrieved_at_utc="2026-10-23T17:00:00Z",
        )


def test_fetch_sec_universe_uses_official_host_and_records_retrieval_time():
    seen = []

    class FakeResponse:
        def __init__(self):
            self.closed = False
        def read(self):
            return payload().encode("utf-8")
        def close(self):
            self.closed = True

    response = FakeResponse()

    def opener(request, timeout):
        seen.append((request.full_url, request.get_header("User-agent"), timeout))
        return response

    universe, metadata = fetch_sec_universe(
        ["AAPL"], user_agent="us-research contact@example.com", opener=opener,
        now=lambda: datetime(2026, 10, 23, 17, 0, tzinfo=timezone.utc),
    )
    assert seen[0][0] == SEC_TICKERS_URL
    assert "contact@example.com" in seen[0][1]
    assert metadata["retrieved_at_utc"] == "2026-10-23T17:00:00Z"
    assert universe[0]["cik"] == "0000320193"
    assert response.closed is True


def test_load_requested_tickers_deduplicates_and_rejects_empty(tmp_path):
    path = tmp_path / "watchlist.txt"
    path.write_text("# current prospective watchlist\nAAPL\nMSFT\nAAPL\n", encoding="utf-8")
    assert load_requested_tickers(path) == ["AAPL", "MSFT"]
    path.write_text("# no symbols\n", encoding="utf-8")
    with pytest.raises(ValueError, match="at least one ticker"):
        load_requested_tickers(path)
