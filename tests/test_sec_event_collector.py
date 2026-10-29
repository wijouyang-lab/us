import json
from datetime import datetime, timezone
from urllib.parse import urlparse

import pytest

from tools.research.sec_event_collector import (
    SecEventCollector,
    load_universe,
    normalize_cik,
)


class FakeResponse:
    def __init__(self, text, status=200):
        self._text = text.encode("utf-8")
        self.status = status
        self.headers = {}

    def read(self):
        return self._text

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def submissions_payload():
    return {
        "name": "Example Corp",
        "filings": {
            "recent": {
                "accessionNumber": [
                    "0000320193-26-000001",
                    "0000320193-26-000002",
                ],
                "form": ["8-K", "4"],
                "filingDate": ["2026-10-22", "2026-10-22"],
                "acceptanceDateTime": [
                    "2026-10-22T16:30:00Z",
                    "2026-10-22T16:31:00Z",
                ],
                "primaryDocument": ["current.htm", "ownership.xml"],
                "items": ["2.02, 9.01", ""],
            }
        },
    }


def test_normalize_cik_and_load_universe(tmp_path):
    assert normalize_cik("320193") == "0000320193"
    with pytest.raises(ValueError, match="invalid CIK"):
        normalize_cik("abc")

    universe_file = tmp_path / "universe.json"
    universe_file.write_text(
        json.dumps([{"cik": "320193", "ticker": "aapl"}]),
        encoding="utf-8",
    )
    assert load_universe(universe_file) == [{"cik": "0000320193", "ticker": "AAPL"}]


def test_collector_fetches_official_headers_and_uses_verified_local_acceptance_time():
    urls = []
    sleeps = []
    header_url = (
        "https://www.sec.gov/Archives/edgar/data/320193/"
        "000032019326000001/0000320193-26-000001-index-headers.html"
    )
    header_text = (
        "<SEC-DOCUMENT>\\n"
        "<ACCEPTANCE-DATETIME>20261022093000\\n"
        "ACCESSION NUMBER: 0000320193-26-000001\\n"
    )

    def opener(request, timeout):
        url = request.full_url
        urls.append(url)
        if url.endswith("/submissions/CIK0000320193.json"):
            return FakeResponse(json.dumps(submissions_payload()))
        if url == header_url:
            return FakeResponse(header_text)
        raise AssertionError(f"unexpected URL: {url}")

    fixed_now = datetime(2026, 10, 23, 14, 0, tzinfo=timezone.utc)
    collector = SecEventCollector(
        "Quant research tester@quantlab.dev",
        opener=opener,
        sleep=sleeps.append,
        now=lambda: fixed_now,
    )
    result = collector.collect_company(
        "320193",
        "AAPL",
        start_date="2026-10-22",
        end_date="2026-10-22",
        max_filings=10,
    )
    assert urls == [
        "https://data.sec.gov/submissions/CIK0000320193.json",
        header_url,
    ]
    assert sleeps == [0.15]
    assert len(result["events"]) == 1
    event = result["events"][0]
    assert event["event_type"] == "earnings"
    assert event["published_at_utc"] == "2026-10-22T14:30:00Z"
    assert event["first_seen_at_utc"] == "2026-10-23T14:00:00Z"
    assert event["availability_status"] == "available"
    assert event["publication_timestamp_source"] == "sec_sgml_acceptance_datetime"
    assert event["source_url"] == header_url
    assert len(event["source_header_sha256"]) == 64
    assert result["metadata"]["verified_header_timestamp_count"] == 1
    assert result["metadata"]["header_fetch_error_count"] == 0
    assert "must not be treated" in result["metadata"]["historical_pit_warning"]


def test_collector_flags_recent_history_gap_and_does_not_infer_release_from_filing_date():
    payload = submissions_payload()
    urls = []

    def opener(request, timeout):
        urls.append(request.full_url)
        if request.full_url.endswith("/submissions/CIK0000320193.json"):
            return FakeResponse(json.dumps(payload))
        return FakeResponse(
            "<SEC-DOCUMENT>\\n<ACCEPTANCE-DATETIME>20261022093000\\n"
            "ACCESSION NUMBER: 0000320193-26-000001\\n"
        )

    collector = SecEventCollector(
        "Quant research tester@quantlab.dev",
        opener=opener,
        sleep=lambda _: None,
        now=lambda: datetime(2026, 10, 23, 14, 0, tzinfo=timezone.utc),
    )
    result = collector.collect_company(
        "320193", "AAPL",
        start_date="2026-10-01", end_date="2026-10-22",
        max_filings=10,
    )
    assert result["metadata"]["recent_history_may_be_incomplete"] is True
    assert result["metadata"]["coverage_status"] == "partial"
    assert result["events"][0]["published_at_utc"] == "2026-10-22T14:30:00Z"
    assert result["events"][0]["sec_filing_date"] == "2026-10-22"


def test_collector_marks_header_fetch_failures_instead_of_inventing_timestamps():
    from urllib.error import HTTPError

    def opener(request, timeout):
        if request.full_url.endswith("/submissions/CIK0000320193.json"):
            return FakeResponse(json.dumps(submissions_payload()))
        raise HTTPError(request.full_url, 404, "not found", {}, None)

    collector = SecEventCollector(
        "Quant research tester@quantlab.dev",
        opener=opener,
        sleep=lambda _: None,
        now=lambda: datetime(2026, 10, 23, 14, 0, tzinfo=timezone.utc),
        max_retries=0,
    )
    result = collector.collect_company(
        "320193", "AAPL",
        start_date="2026-10-22", end_date="2026-10-22",
    )
    assert len(result["events"]) == 1
    assert result["events"][0]["availability_status"] == "fetch_error"
    assert result["events"][0]["published_at_utc"] is None
    assert result["metadata"]["coverage_status"] == "partial"
    assert result["metadata"]["header_fetch_error_count"] == 1


def test_collector_requires_contact_user_agent_and_restricts_hosts():
    with pytest.raises(ValueError, match="contact email"):
        SecEventCollector("Quant research without contact")
    collector = SecEventCollector(
        "Quant research tester@quantlab.dev",
        opener=lambda *args, **kwargs: pytest.fail("external host must not be called"),
        sleep=lambda _: None,
    )
    with pytest.raises(ValueError, match="only permits HTTPS"):
        collector._request_text("https://example.com/unknown.json")


def test_collector_marks_timestamp_unverified_as_partial_even_if_http_succeeded():
    def opener(request, timeout):
        if request.full_url.endswith("/submissions/CIK0000320193.json"):
            return FakeResponse(json.dumps(submissions_payload()))
        return FakeResponse("<html>no accession or timestamp here</html>")

    collector = SecEventCollector(
        "Quant research tester@quantlab.dev",
        opener=opener,
        sleep=lambda _: None,
        now=lambda: datetime(2026, 10, 23, 14, 0, tzinfo=timezone.utc),
    )
    result = collector.collect_company(
        "320193", "AAPL",
        start_date="2026-10-22", end_date="2026-10-22",
    )
    assert result["events"][0]["published_at_utc"] is None
    assert result["events"][0]["availability_status"] == "timestamp_missing"
    assert result["metadata"]["header_fetch_error_count"] == 0
    assert result["metadata"]["unverified_header_timestamp_count"] == 1
    assert result["metadata"]["coverage_status"] == "partial"


def test_collector_cli_refuses_to_overwrite_existing_snapshot_without_flag(tmp_path, capsys):
    from tools.research.sec_event_collector import main

    universe = tmp_path / "universe.json"
    universe.write_text(json.dumps([{"cik": "320193", "ticker": "AAPL"}]), encoding="utf-8")
    output = tmp_path / "events.json"
    output.write_text("previous immutable snapshot", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        main([
            "--universe", str(universe),
            "--start-date", "2026-10-22",
            "--end-date", "2026-10-23",
            "--output", str(output),
            "--user-agent", "Quant research tester@quantlab.dev",
        ])
    assert exc.value.code == 2
    assert "refusing to overwrite" in capsys.readouterr().err
    assert output.read_text(encoding="utf-8") == "previous immutable snapshot"


def test_collector_cli_requires_distinct_event_and_metadata_outputs(tmp_path, capsys):
    from tools.research.sec_event_collector import main

    universe = tmp_path / "universe.json"
    universe.write_text(json.dumps([{"cik": "320193", "ticker": "AAPL"}]), encoding="utf-8")
    output = tmp_path / "events.json"

    with pytest.raises(SystemExit) as exc:
        main([
            "--universe", str(universe),
            "--start-date", "2026-10-22",
            "--end-date", "2026-10-23",
            "--output", str(output),
            "--metadata-output", str(output),
            "--user-agent", "Quant research tester@quantlab.dev",
        ])
    assert exc.value.code == 2
    assert "must be different files" in capsys.readouterr().err
