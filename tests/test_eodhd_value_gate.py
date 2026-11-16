import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/research"


def test_gap_inventory_counts_and_sums():
    rows = list(csv.DictReader((DATA / "eodhd_price_gap_inventory.csv").open(encoding="utf-8")))
    assert len(rows) == 887
    assert sum(int(r["expected_member_days"]) for r in rows) == 2220522
    assert sum(int(r["observed_member_days"]) for r in rows) == 2113080
    assert sum(int(r["missing_member_days"]) for r in rows) == 107442
    assert sum(1 for r in rows if int(r["observed_member_days"]) == 0) == 80
    assert sum(1 for r in rows if r["ticker_status"] == "REMOVED_OR_DELISTED") == 416
    assert sum(1 for r in rows if r["ticker_status"] == "CURRENT_OR_LATEST") == 471


def test_gap_categories_are_separate():
    rows = list(csv.DictReader((DATA / "eodhd_price_gap_inventory.csv").open(encoding="utf-8")))
    missing_trading = sum(int(r["missing_trading_days"]) for r in rows)
    missing_member = sum(int(r["missing_member_days"]) for r in rows)
    removed_zero = sum(1 for r in rows if r["ticker_status"] == "REMOVED_OR_DELISTED" and int(r["observed_member_days"]) == 0)
    assert missing_trading == 21819
    assert missing_member == 107442
    assert removed_zero == 60
    assert all(r["corporate_actions"] == "NOT_AVAILABLE_SEPARATELY" for r in rows)
    assert all(r["mapping_status"] == "NOT_VERIFIABLE" for r in rows)


def test_incremental_estimate_is_not_a_pass():
    rows = list(csv.DictReader((DATA / "eodhd_incremental_coverage_estimate.csv").open(encoding="utf-8")))
    assert len(rows) == 5
    gate = next(r for r in rows if r["scenario"] == "P9_GATE")
    assert float(gate["ticker_coverage"]) == 0.98
    assert float(gate["member_day_coverage"]) == 0.95
    upper = next(r for r in rows if r["scenario"] == "EODHD_RECOVER_ALL_GAP")
    assert upper["claim_status"] == "UPPER_BOUND_NOT_VERIFIED"
    assert upper["member_day_coverage"] == "1.0"
    assert not any(r["claim_status"] == "PASS" for r in rows)


def test_download_cost_is_one_month_and_no_vps():
    d = json.loads((DATA / "eodhd_download_cost_estimate.json").read_text(encoding="utf-8"))
    assert d["price_usd_per_month"] <= 20
    assert d["max_subscription_months"] == 1
    assert d["vps_required"] is False
    assert d["calls"]["total"] == 2662
    assert d["calls"]["daily_limit"] == 100000
    assert d["license"]["retain_after_cancel"] is True
    assert d["license"]["redistribution"] is False


def test_report_has_no_buy_and_retention_conditions():
    doc = (ROOT / "docs/research/P10_5_EODHD_ONE_MONTH_VALUE_GATE.md").read_text(encoding="utf-8")
    assert "NO_BUY" in doc
    assert "$19.99" in doc
    assert "MAX_SUBSCRIPTION: 1 MONTH" in doc
    assert "MAX_BUDGET_USD: 20" in doc
    assert "POST_CANCELLATION_RAW_DATA_RETENTION_REQUIRED: YES" in doc
    assert "95%" in doc and "98%" in doc


def test_no_vendor_raw_files_committed():
    files = [p for p in DATA.glob("eodhd_*")]
    assert all(p.suffix in {".csv", ".json"} for p in files)
    assert not list(DATA.glob("*.parquet"))
    assert not list(DATA.glob("*.sqlite"))
