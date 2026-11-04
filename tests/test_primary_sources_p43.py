# -*- coding: utf-8 -*-
import json
from pathlib import Path
import pytest
from tools.investment_research.dividend.sec_filing_fetcher import archive_dir, index_url, extract_split_text, FilingFetcher
from tools.investment_research.dividend.dividend_event_collector import normalize, dedupe


def test_archive_dir_removes_dashes_and_leading_zero():
    assert archive_dir("0000320193", "0000320193-20-000096") == \
        "https://www.sec.gov/Archives/edgar/data/320193/000032019320000096"
    assert index_url("0000320193", "0000320193-20-000096").endswith("/index.json")


def test_split_ratio_forward_and_reverse():
    assert extract_split_text("four-for-one stock split effective August 31, 2020")["ratio"] == 4.0
    assert extract_split_text("1-for-10 reverse stock split effective January 2, 2020")["ratio"] == 0.1


def test_split_dates_extracted_only_from_text():
    x = extract_split_text("The 4-for-1 stock split will be effective August 31, 2020.")
    assert x["dates"] == ["August 31, 2020"]


def test_placeholder_ua_rejected_without_audit_flag(monkeypatch):
    monkeypatch.delenv("ALLOW_SEC_PLACEHOLDER", raising=False)
    with pytest.raises(RuntimeError):
        FilingFetcher(Path("tmp"), "contact@example.com")


def test_actual_split_records_are_not_promoted():
    d = json.loads(Path("data/research/split_evidence_p43.json").read_text())
    assert len(d) == 22
    assert all(x["status"] == "PARTIALLY_VERIFIED" for x in d)
    assert all(x["filing"]["status_text"] == "FETCHED" for x in d)
    assert all(x["extraction"]["ratio"] is None for x in d)


def test_actual_event_records_have_sources_and_no_fake_ex_date():
    d = json.loads(Path("data/research/dividend_events_p43.json").read_text())
    assert d["summary"]["verified"] == 0
    assert d["summary"]["partially_verified"] == len(d["events"])
    for e in d["events"]:
        assert e["source_url"].startswith("https://www.sec.gov/")
        assert e["evidence_sha256"] and e["accession_number"]
        assert e["ex_date"] is None


def test_event_same_source_dedupe():
    base = dict(ticker="X", cik="1", event_type="DECLARED", announcement_date="2025-05-01",
                source_url="https://www.sec.gov/x", source_type="SEC 8-K", evidence_sha256="a"*64)
    assert len(dedupe([normalize(base), normalize(base)])) == 1


def test_different_company_not_merged():
    base = dict(ticker="X", cik="1", event_type="DECLARED", announcement_date="2025-05-01",
                source_url="https://www.sec.gov/x", source_type="SEC 8-K", evidence_sha256="a"*64)
    assert len(dedupe([normalize(base), normalize({**base, "ticker": "Y"})])) == 2


def test_empty_search_is_not_no_dividend():
    d = json.loads(Path("data/research/dividend_events_p43.json").read_text())
    assert d["summary"]["status"] in ("EVENT_CANDIDATES_FOUND", "NO_EVENT_EVIDENCE_IN_FETCHED_FILINGS")
    assert "NO_DIVIDEND" not in d["summary"]["status"]


def test_scores_not_increased_by_evidence():
    d = json.loads(Path("data/research/dividend_quality_p43.json").read_text())
    ready = [t for t, v in d["tickers"].items() if v["score_status"] == "SCORE_READY"]
    assert len(ready) == 10
