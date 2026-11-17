import csv
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/research"
P = DATA / "p12_3_1"


def _rows(path):
    return list(csv.DictReader(path.open(encoding="utf-8")))


def test_asof_returns_all_periods_and_no_future_leak():
    from tools.research.p12.pit_query import as_of
    panel = pd.read_csv(DATA / "p12_3/p12_3_accession_fact_panel.csv", dtype={"cik": str})
    panel["cik"] = panel.cik.str.zfill(10)
    q = as_of(panel, "0000320193", "Revenue", "2015-06-30")
    assert q.period_end.nunique() >= 3
    assert len(q) > q.period_end.nunique()
    assert q["known_at"].max() <= pd.Timestamp("2015-06-30T23:59:59Z")
    # A later query may see more periods, never fewer.
    q2 = as_of(panel, "0000320193", "Revenue", "2020-12-31")
    assert q2.period_end.nunique() >= q.period_end.nunique()


def test_same_day_timestamp_and_revision_boundary():
    from tools.research.p12.pit_query import as_of
    panel = pd.read_csv(DATA / "p12_3/p12_3_accession_fact_panel.csv", dtype={"cik": str})
    panel["cik"] = panel.cik.str.zfill(10)
    before = as_of(panel, "0000001800", "Capex", "2018-08-01T19:00:00Z")
    after = as_of(panel, "0000001800", "Capex", "2018-08-01T21:00:00Z")
    assert len(after) > len(before)
    assert "0001104659-18-048736" not in set(before.accession)
    assert "0001104659-18-048736" in set(after.accession)
    later = as_of(panel, "0000001800", "Capex", "2019-08-01")
    assert "0001410578-19-000606" in set(later.accession)


def test_event_statuses_are_mutually_exclusive_and_total():
    e = _rows(P / "p12_3_1_event_window_returns.csv")
    assert len(e) == 13668
    statuses = {}
    for r in e:
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1
    assert sum(statuses.values()) == 13668
    assert statuses == {
        "OK_COMPLETE": 10941,
        "FOREIGN_PRICE_MISSING": 2056,
        "US_SYMBOL_NOT_FOUND": 619,
        "NO_PREVIOUS_CLOSE": 46,
        "D5_MISSING": 3,
        "NO_EVENT_CLOSE": 2,
        "D1_MISSING": 1,
    }
    assert sum(1 for r in e if r["d0_return"]) == 10945
    assert sum(1 for r in e if r["d1_return"]) == 10944
    assert sum(1 for r in e if r["d5_return"]) == 10941
    non = [r for r in e if r["event_session"] == "NON_TRADING"]
    assert len(non) == 20
    assert sum(1 for r in non if r["status"] == "OK_COMPLETE") == 15


def test_10q_and_amendment_validation():
    rows = _rows(P / "p12_3_1_fact_version_validation.csv")
    assert len(rows) == 16
    assert any(r["form"] == "10-Q/A" for r in rows)
    statuses = {}
    for r in rows:
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1
    assert statuses.get("MATCH") == 10
    assert statuses.get("PERIOD_AGGREGATION_MISMATCH") == 6
    assert statuses.get("CONFLICT", 0) == 0


def test_asof_evidence_quality_and_report():
    tests = _rows(P / "p12_3_1_asof_query_tests.csv")
    assert len(tests) == 6
    assert all(r["status"] == "OK" for r in tests)
    q = {r["metric"]: r for r in _rows(P / "p12_3_1_quality_summary.csv")}
    assert q["events_total"]["value"] == "13668"
    doc = (ROOT / "docs/research/P12_3_1_PIT_QUERY_EVENT_WINDOW_AUDIT.md").read_text(encoding="utf-8")
    assert "P12_3_1_STATUS: READY_RESTRICTED" in doc
    assert "EVENT_STATUS_COMPLETE: 13,668 / 13,668" in doc
    assert "MARKET_WIDE_PIT: DATA_BLOCKED" in doc
    assert "ALL 8 NO-GO" in doc
    assert json.loads((DATA / "p12_3/p12_3_run_manifest.json").read_text())["raw_sec_json_committed"] is False
    assert not list(DATA.glob("*.parquet"))
