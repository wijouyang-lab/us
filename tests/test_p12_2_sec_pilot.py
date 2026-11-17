import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/research"
P = DATA / "p12_2"


def _rows(path):
    return list(csv.DictReader(path.open(encoding="utf-8")))


def test_sample_is_fixed_40_and_grouped():
    rows = _rows(DATA / "p12_2_sample_universe.csv")
    assert len(rows) == 40
    groups = {}
    for r in rows:
        groups[r["group"]] = groups.get(r["group"], 0) + 1
    assert groups == {"US_CURRENT": 30, "US_NON_SURVIVING": 5, "FOREIGN_ADR": 5}
    assert all(len(r["cik"]) == 10 for r in rows)
    assert len({r["cik"] for r in rows}) == 40


def test_fact_panel_is_accession_level():
    rows = _rows(P / "p12_2_accession_fact_panel.csv")
    assert len(rows) == 59897
    assert len({r["cik"] for r in rows}) == 40
    assert len({r["metric"] for r in rows}) == 10
    assert all(r["accession"] for r in rows)
    assert all(r["source_url"].startswith("https://www.sec.gov/Archives/") for r in rows)


def test_8k_and_6k_events_are_separate():
    rows = _rows(P / "p12_2_filing_events.csv")
    assert len(rows) == 4808
    assert sum(1 for r in rows if r["event_type"] == "8-K") == 2752
    assert sum(1 for r in rows if r["event_type"] == "6-K") == 2056
    assert all(r["acceptance_datetime"] for r in rows)
    assert sum(1 for r in rows if r["price_match"].lower() == "true") == 2752
    assert sum(1 for r in rows if r["reaction_return"]) == 2706


def test_required_8k_items_are_covered():
    rows = {str(r["item"]): r for r in _rows(P / "p12_2_8k_item_coverage.csv")}
    for item in ("1.01", "2.01", "2.02", "5.02", "7.01", "8.01"):
        assert item in rows
    assert int(rows["2.02"]["events"]) > 0
    assert all("acceptance_missing" in r for r in rows.values())


def test_pit_quality_and_annual_coverage():
    q = {r["metric"]: r for r in _rows(P / "p12_2_pit_quality_summary.csv")}
    assert q["sample_issuers"]["value"] == "40"
    assert q["8k_acceptance_missing"]["value"] == "0"
    assert q["foreign_events_price_missing"]["status"] == "DATA_BLOCKED"
    annual = _rows(P / "p12_2_annual_coverage.csv")
    assert len(annual) == 590
    assert annual[0]["year"] == "2009"
    assert annual[-1]["year"] == "2024"


def test_manifest_and_report_status():
    m = json.loads((P / "p12_2_run_manifest.json").read_text(encoding="utf-8"))
    assert m["raw_sec_json_committed"] is False
    assert m["raw_price_committed"] is False
    doc = (ROOT / "docs/research/P12_2_SEC_PIT_EVENT_PILOT.md").read_text(encoding="utf-8")
    assert "P12_2_STATUS: READY_RESTRICTED" in doc
    assert "MARKET_WIDE_PIT: DATA_BLOCKED" in doc
    assert "EXACT_EARNINGS_TIME: DATA_BLOCKED" in doc
    assert "INTRADAY_REACTION: DATA_BLOCKED" in doc
    assert "ALL 8 NO-GO" in doc
    assert "NO_BUY" in doc
    assert not list(DATA.glob("*.parquet"))
    assert not list(DATA.glob("*.pkl"))
