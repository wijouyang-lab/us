import csv
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/research"
P = DATA / "p12_3"


def _rows(path):
    return list(csv.DictReader(path.open(encoding="utf-8")))


def test_expanded_sample_and_fact_panel():
    s = _rows(DATA / "p12_3_expanded_universe.csv")
    assert len(s) == 140
    assert len({r["cik"] for r in s}) == 140
    groups = {}
    for r in s:
        groups[r["group"]] = groups.get(r["group"], 0) + 1
    assert groups == {"US_CURRENT": 30, "US_CURRENT_EXPANSION": 100, "US_NON_SURVIVING": 5, "FOREIGN_ADR": 5}
    f = _rows(P / "p12_3_accession_fact_panel.csv")
    assert len(f) == 222804
    assert len({r["cik"] for r in f}) == 139
    assert len({r["metric"] for r in f}) == 10


def test_events_and_corrected_windows():
    e = _rows(P / "p12_3_event_window_returns.csv")
    assert len(e) == 13668
    assert sum(1 for r in e if r["event_type"] == "8-K") == 11612
    assert sum(1 for r in e if r["event_type"] == "6-K") == 2056
    assert all(r["acceptance_datetime"] for r in e)
    assert sum(1 for r in e if r["event_price_status"] == "OK") == 10930
    assert sum(1 for r in e if r["price_match"].lower() == "false") == 2675
    assert any(r["event_session"] == "AFTER_HOURS" and "NEXT_CLOSE_VS_EVENT_CLOSE" in r["window_rule"] for r in e)
    assert any(r["event_session"] == "NON_TRADING" for r in e)


def test_raw_filing_validation():
    filings = _rows(P / "p12_3_filing_validation.csv")
    checks = _rows(P / "p12_3_fact_reconciliation.csv")
    assert len(filings) == 10
    assert all(r["status"] == "PARSED" for r in filings)
    assert len(checks) == 60
    statuses = {}
    for r in checks:
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1
    assert statuses.get("MATCH") == 59
    assert statuses.get("PANEL_MISSING") == 1
    assert statuses.get("CONFLICT", 0) == 0


def test_version_history_and_pit_query():
    from tools.research.p12.pit_query import as_of
    panel = pd.read_csv(P / "p12_3_accession_fact_panel.csv", dtype={"cik": str})
    panel["cik"] = panel.cik.str.zfill(10)
    v = _rows(P / "p12_3_version_history.csv")
    assert len(v) == 67159
    multi = next(r for r in v if int(r["version_count"]) > 1 and "nan" not in r["acceptance_datetimes"])
    dates = multi["acceptance_datetimes"].split("|")
    first_day = dates[0][:10]
    q = as_of(panel, multi["cik"], multi["metric"], first_day)
    assert not q.empty
    known = q[q["acceptance_datetime"].notna()]
    assert not known.empty
    assert known.iloc[0]["acceptance_datetime"][:10] <= first_day


def test_annual_quarterly_coverage():
    a = _rows(P / "p12_3_annual_coverage.csv")
    q = _rows(P / "p12_3_quarterly_coverage.csv")
    assert len(a) == 2010
    assert a[0]["year"] == "2009" and a[-1]["year"] == "2024"
    assert len(q) == 7465


def test_report_and_manifest():
    doc = (ROOT / "docs/research/P12_3_SEC_PIT_DATA_VALIDATION.md").read_text(encoding="utf-8")
    assert "P12_3_STATUS: READY_RESTRICTED" in doc
    assert "MARKET_WIDE_PIT: DATA_BLOCKED" in doc
    assert "EXACT_EARNINGS_TIME: DATA_BLOCKED" in doc
    assert "INTRADAY_REACTION: DATA_BLOCKED" in doc
    assert "ALL 8 NO-GO" in doc
    assert "NO_BUY" in doc
    m = json.loads((P / "p12_3_run_manifest.json").read_text(encoding="utf-8"))
    assert m["raw_sec_json_committed"] is False
    assert m["raw_price_committed"] is False
    assert not list(DATA.glob("*.parquet"))
    assert not list(DATA.glob("*.pkl"))
