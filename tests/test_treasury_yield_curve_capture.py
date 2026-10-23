from datetime import datetime, timezone

import pytest

from tools.research.treasury_yield_curve_capture import (
    BASE_URL,
    fetch_treasury_yield_curve,
    parse_treasury_yield_curve_xml,
)


def sample_xml():
    return """<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom"
          xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
          xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices">
      <entry><content type="application/xml"><m:properties>
        <d:NEW_DATE>2026-10-20T00:00:00</d:NEW_DATE>
        <d:BC_3MONTH>4.0</d:BC_3MONTH><d:BC_2YEAR>4.2</d:BC_2YEAR>
        <d:BC_10YEAR>4.5</d:BC_10YEAR>
      </m:properties></content></entry>
      <entry><content type="application/xml"><m:properties>
        <d:NEW_DATE>2026-10-21T00:00:00</d:NEW_DATE>
        <d:BC_3MONTH>4.1</d:BC_3MONTH><d:BC_2YEAR>4.1</d:BC_2YEAR>
        <d:BC_10YEAR>4.6</d:BC_10YEAR>
      </m:properties></content></entry>
      <entry><content type="application/xml"><m:properties>
        <d:NEW_DATE>2026-10-22T00:00:00</d:NEW_DATE>
        <d:BC_3MONTH>4.2</d:BC_3MONTH><d:BC_2YEAR></d:BC_2YEAR>
        <d:BC_10YEAR>4.7</d:BC_10YEAR>
      </m:properties></content></entry>
    </feed>"""


def test_parse_yield_curve_builds_spreads_and_daily_changes_without_zero_fill():
    result = parse_treasury_yield_curve_xml(
        sample_xml(),
        retrieved_at_utc="2026-10-23T16:00:00Z",
        source_url=BASE_URL + "?data=daily_treasury_yield_curve&field_tdr_date_value=2026",
    )
    assert result["metadata"]["row_count"] == 3
    first, second, third = result["rows"]
    assert first["slope_2s10s_bp"] == 30.0
    assert first["slope_3m10y_bp"] == 50.0
    assert first["change_2y_bp"] is None
    assert second["change_2y_bp"] == -10.0
    assert second["change_10y_bp"] == 10.0
    assert second["change_2s10s_bp"] == 20.0
    assert third["yield_pct"]["2y"] is None
    assert third["slope_2s10s_bp"] is None
    assert third["change_2y_bp"] is None
    assert third["retrieved_at_utc"] == "2026-10-23T16:00:00Z"
    assert third["availability_rule"] == "usable_only_at_or_after_retrieved_at_utc"
    assert result["metadata"]["production_scanner_modified"] is False


def test_parser_rejects_naive_timestamp_bad_xml_and_untrusted_host():
    with pytest.raises(ValueError, match="timezone-aware"):
        parse_treasury_yield_curve_xml(
            sample_xml(),
            retrieved_at_utc="2026-10-23T16:00:00",
            source_url=BASE_URL,
        )
    with pytest.raises(ValueError, match="invalid Treasury yield curve XML"):
        parse_treasury_yield_curve_xml(
            "<feed>",
            retrieved_at_utc="2026-10-23T16:00:00Z",
            source_url=BASE_URL,
        )
    with pytest.raises(ValueError, match="allowlist"):
        parse_treasury_yield_curve_xml(
            sample_xml(),
            retrieved_at_utc="2026-10-23T16:00:00Z",
            source_url="https://example.com/yields.xml",
        )


class FakeResponse:
    def __init__(self, body):
        self.body = body.encode("utf-8")
        self.closed = False

    def read(self):
        return self.body

    def close(self):
        self.closed = True


def test_fetch_uses_official_endpoint_and_records_actual_retrieval_time():
    seen = []
    response = FakeResponse(sample_xml())

    def opener(request, timeout):
        seen.append((request.full_url, request.get_header("User-agent"), timeout))
        return response

    result = fetch_treasury_yield_curve(
        2026,
        opener=opener,
        now=lambda: datetime(2026, 10, 23, 16, 0, tzinfo=timezone.utc),
    )
    assert seen[0][0] == BASE_URL + "?data=daily_treasury_yield_curve&field_tdr_date_value=2026"
    assert "research-only" in seen[0][1]
    assert result["metadata"]["row_count"] == 3
    assert response.closed is True


def test_fetch_rejects_year_before_source_coverage():
    with pytest.raises(ValueError, match="between 1990 and 9999"):
        fetch_treasury_yield_curve(1989)



def test_real_yield_curve_uses_real_data_key_and_maturity_fields():
    xml = """<feed xmlns="http://www.w3.org/2005/Atom"
        xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
        xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices">
      <entry><content><m:properties>
        <d:NEW_DATE>2026-10-22T00:00:00</d:NEW_DATE>
        <d:BC_5YEAR>1.8</d:BC_5YEAR><d:BC_7YEAR>2.0</d:BC_7YEAR>
        <d:BC_10YEAR>2.1</d:BC_10YEAR><d:BC_20YEAR>2.3</d:BC_20YEAR>
        <d:BC_30YEAR>2.4</d:BC_30YEAR>
      </m:properties></content></entry>
    </feed>"""
    result = parse_treasury_yield_curve_xml(
        xml,
        retrieved_at_utc="2026-10-23T16:00:00Z",
        source_url=BASE_URL + "?data=daily_treasury_real_yield_curve&field_tdr_date_value=2026",
        curve_type="real",
    )
    assert result["metadata"]["source"] == "us_treasury_daily_par_real_yield_curve"
    assert result["metadata"]["curve_type"] == "real"
    assert result["metadata"]["source_diagnostics"]["xml_entry_count"] == 1
    assert result["metadata"]["source_diagnostics"]["entries_with_valid_observation_date"] == 1
    assert result["metadata"]["source_diagnostics"]["entries_with_any_maturity_yield"] == 1
    assert result["rows"][0]["yield_pct"]["5y"] == 1.8
    assert result["rows"][0]["yield_pct"]["10y"] == 2.1
    assert result["rows"][0]["slope_2s10s_bp"] is None


def test_fetch_real_curve_uses_official_real_curve_key():
    seen = []
    response = FakeResponse(sample_xml())

    def opener(request, timeout):
        seen.append(request.full_url)
        return response

    result = fetch_treasury_yield_curve(
        2026,
        opener=opener,
        now=lambda: datetime(2026, 10, 23, 16, 0, tzinfo=timezone.utc),
        curve_type="real",
    )
    assert "data=daily_treasury_real_yield_curve" in seen[0]
    assert result["metadata"]["curve_type"] == "real"
