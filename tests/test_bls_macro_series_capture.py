import json
from datetime import datetime, timezone

import pytest

from tools.research.bls_macro_series_capture import (
    API_URL,
    fetch_bls_macro_snapshot,
    parse_bls_api_response,
)


def payload():
    return {
        "status": "REQUEST_SUCCEEDED",
        "Results": {"series": [
            {"seriesID": "CUSR0000SA0", "data": [
                {"year": "2026", "period": "M08", "periodName": "August", "value": "323.4"},
                {"year": "2026", "period": "M09", "periodName": "September", "value": "324.1"},
            ]},
            {"seriesID": "LNS14000000", "data": [
                {"year": "2026", "period": "M09", "periodName": "September", "value": "4.2"},
            ]},
        ]},
    }


def test_parse_bls_api_uses_latest_monthly_observation_and_preserves_missing_series():
    result = parse_bls_api_response(
        json.dumps(payload()),
        retrieved_at_utc="2026-10-23T17:00:00Z",
    )
    assert result["metadata"]["available_series_count"] == 2
    cpi = next(row for row in result["series"] if row["series_id"] == "CUSR0000SA0")
    assert cpi["latest_observation"]["observation_period"] == "2026-M09"
    assert cpi["latest_observation"]["value"] == 324.1
    unemployment = next(row for row in result["series"] if row["series_id"] == "LNS14000000")
    assert unemployment["latest_observation"]["value"] == 4.2
    missing = next(row for row in result["series"] if row["series_id"] == "CES0000000001")
    assert missing["latest_observation"] is None
    assert missing["value_available"] is False
    assert result["metadata"]["research_only"] is True
    assert "historical vintage" in " ".join(result["metadata"]["limitations"])


def test_parse_bls_api_rejects_bad_json_status_and_untrusted_host():
    with pytest.raises(ValueError, match="invalid BLS API JSON"):
        parse_bls_api_response("not json", retrieved_at_utc="2026-10-23T17:00:00Z")
    bad = {"status": "REQUEST_FAILED", "message": ["bad request"]}
    with pytest.raises(ValueError, match="did not succeed"):
        parse_bls_api_response(json.dumps(bad), retrieved_at_utc="2026-10-23T17:00:00Z")
    with pytest.raises(ValueError, match="host allowlist"):
        parse_bls_api_response(
            json.dumps(payload()), retrieved_at_utc="2026-10-23T17:00:00Z",
            source_url="https://example.com/api",
        )


class FakeResponse:
    def __init__(self, body):
        self.body = body
        self.closed = False

    def read(self):
        return self.body

    def close(self):
        self.closed = True


def test_fetch_uses_public_api_without_key_and_records_actual_retrieval_time():
    seen = []
    response = FakeResponse(json.dumps(payload()).encode())

    def opener(request, timeout):
        seen.append((request.full_url, request.get_header("Content-type"), request.data, timeout))
        return response

    result = fetch_bls_macro_snapshot(
        start_year=2024,
        end_year=2026,
        opener=opener,
        now=lambda: datetime(2026, 10, 23, 17, 0, tzinfo=timezone.utc),
    )
    assert seen[0][0] == API_URL
    assert seen[0][1] == "application/json"
    assert b"registrationkey" not in seen[0][2].lower()
    assert result["metadata"]["retrieved_at_utc"] == "2026-10-23T17:00:00Z"
    assert response.closed is True


def test_fetch_rejects_invalid_year_range():
    with pytest.raises(ValueError, match="invalid BLS API year range"):
        fetch_bls_macro_snapshot(start_year=2027, end_year=2026)
