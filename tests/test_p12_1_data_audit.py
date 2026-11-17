import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/research"


def _rows(name):
    return list(csv.DictReader((DATA / name).open(encoding="utf-8")))


def test_source_inventory_has_required_dimensions_and_statuses():
    rows = _rows("p12_1_data_source_inventory.csv")
    assert len(rows) == 14
    required = {
        "source", "type", "history_start", "history_end", "stock_coverage",
        "delisted", "pit_timing", "delay", "missing_rate", "free_limit",
        "cost", "license", "status", "notes", "evidence_url",
    }
    assert required <= set(rows[0])
    statuses = {r["status"] for r in rows}
    assert "READY_RESTRICTED" in statuses
    assert "DATA_BLOCKED" in statuses
    assert "NO_BUY" in statuses


def test_sec_filing_sample_is_small_and_not_full_market():
    rows = _rows("p12_1_filing_coverage_by_year.csv")
    assert rows[0]["year"] == "1995"
    assert rows[-1]["year"] == "2026"
    assert sum(int(r["filings"]) for r in rows) == 9426
    summary = {r["dataset"]: r for r in _rows("p12_1_stock_coverage_summary.csv")}
    assert summary["SEC_filing_history_sample"]["tickers"] == "144"
    assert summary["SP500_price_panel"]["tickers"] == "1017"
    assert summary["P6_current_fundamentals"]["status"] == "DATA_BLOCKED"


def test_report_separates_ready_restricted_and_blocked():
    doc = (ROOT / "docs/research/P12_1_EVENT_FUNDAMENTAL_DATA_AUDIT.md").read_text(encoding="utf-8")
    assert "P12_1_STATUS: PARTIAL" in doc
    assert "MACRO_PIT: READY_RESTRICTED" in doc
    assert "SEC_FILING_EVENTS: READY_RESTRICTED" in doc
    assert "MARKET_WIDE_FUNDAMENTAL_PIT: DATA_BLOCKED" in doc
    assert "EARNINGS_TIMING: DATA_BLOCKED" in doc
    assert "NEWS_SENTIMENT: DATA_BLOCKED" in doc
    assert "ANALYST_EXPECTATIONS: NO_BUY" in doc


def test_preserves_prior_conclusions_and_no_purchase():
    doc = (ROOT / "docs/research/P12_1_EVENT_FUNDAMENTAL_DATA_AUDIT.md").read_text(encoding="utf-8")
    assert "ALL 8 NO-GO" in doc
    assert "NO_BUY" in doc
    assert "IBKR_CONNECTED: NO" in doc
    assert "NO_PURCHASE: YES" in doc
    assert not list(DATA.glob("*.parquet"))
    assert not list(DATA.glob("*.pkl"))
