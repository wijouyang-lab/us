import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/research"


def _rows(name):
    return list(csv.DictReader((DATA / name).open(encoding="utf-8")))


def test_universe_inventory_has_required_sources():
    rows = {r["dataset"]: r for r in _rows("p11_1_universe_inventory.csv")}
    assert set(rows) >= {
        "SP500_price_panel", "SP500_membership", "P6_value_rankings",
        "P6_quality_rankings", "P6_garp_rankings", "SEC_filing_history",
        "news_translations", "P10_6_SEC_pilot", "macro_panel", "IBKR_broker",
    }
    assert rows["SP500_price_panel"]["tickers"] == "983"
    assert rows["P6_value_rankings"]["tickers"] == "5453"
    assert rows["SEC_filing_history"]["tickers"] == "144"
    assert rows["P10_6_SEC_pilot"]["usable_for_p11"] == "NO_GO"


def test_factor_readiness_separates_price_from_fundamentals_and_news():
    rows = _rows("p11_1_factor_readiness.csv")
    price = [r for r in rows if r["group"] == "A_price"]
    assert price
    assert all(r["can_backtest"] == "YES_RESTRICTED" for r in price)
    fundamentals = [r for r in rows if r["group"] == "B_fundamental"]
    assert fundamentals
    assert all(r["can_backtest"] == "NO_PIT" for r in fundamentals)
    events = [r for r in rows if r["group"] == "C_events"]
    news = [r for r in rows if r["group"] == "D_news"]
    assert all(r["can_backtest"] in {"NO", "NO_PIT"} for r in events)
    assert all(r["can_backtest"] == "NO" for r in news)


def test_p11_1_status_is_partial_and_does_not_claim_full_market():
    doc = (ROOT / "docs/research/P11_1_EXISTING_DATA_AND_RESEARCH_AUDIT.md").read_text(encoding="utf-8")
    assert "P11_1_STATUS: PARTIAL" in doc
    assert "PRICE_FACTOR_RESEARCH: READY_RESTRICTED" in doc
    assert "FULL_MARKET_CLAIM: NO_GO" in doc
    assert "FUNDAMENTAL_PIT_RESEARCH: NO_GO" in doc
    assert "EVENT_INCREMENT_RESEARCH: NO_GO" in doc
    assert "NEWS_MACRO_RESEARCH: NO_GO" in doc


def test_no_raw_market_data_or_broker_connection():
    assert not list(DATA.glob("*.parquet"))
    assert not list(DATA.glob("*.pkl"))
    assert not list(DATA.glob("*.sqlite"))
    doc = (ROOT / "docs/research/P11_1_EXISTING_DATA_AND_RESEARCH_AUDIT.md").read_text(encoding="utf-8")
    assert "IBKR_CONNECTED: NO" in doc
    assert "PAPER_50000_USED: NO" in doc
