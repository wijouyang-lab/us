import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/research"


def _rows(name):
    return list(csv.DictReader((DATA / name).open(encoding="utf-8")))


def test_source_manifest_hashes_and_rows():
    rows = {r["file"]: r for r in _rows("p10_5_2_source_manifest.csv")}
    assert set(rows) == {
        "sp500_daily.csv", "spy.csv", "finsaber_prices_raw.csv",
        "data_audit.json", "pit_coverage_summary.json", "pit_coverage_by_ticker.csv",
    }
    assert rows["sp500_daily.csv"]["bytes"] == "5533628"
    assert rows["sp500_daily.csv"]["sha256"].startswith("646b2e47")
    assert rows["spy.csv"]["rows"] == "6311"
    assert rows["finsaber_prices_raw.csv"]["bytes"] == "265180873"
    assert rows["finsaber_prices_raw.csv"]["sha256"] == "f67e3972dceefbbdf6c17b84b30957a7b83518401955fff8ae0bc4ae206fa83f"
    assert rows["finsaber_prices_raw.csv"]["rows"] == "4736109"
    assert rows["pit_coverage_by_ticker.csv"]["rows"] == "1062"


def test_v2_increment_is_24_new_plus_6_existing():
    rows = _rows("p10_5_2_v2_incremental_ticker_diff.csv")
    assert len(rows) == 30
    new = [r for r in rows if r["change_type"] == "NEW_COVERAGE"]
    existing = [r for r in rows if r["change_type"] == "EXISTING_ADDED"]
    assert len(new) == 24
    assert len(existing) == 6
    assert sum(int(r["added_member_days"]) for r in rows) == 11802
    assert {r["ticker"] for r in new} >= {"BRK.B", "BF.B", "CRWD", "PLTR", "SMCI", "VST", "WDAY"}
    assert sum(int(r["added_member_days"]) for r in existing) == 514


def test_verified_identity_counts_and_conflicts():
    rows = _rows("p10_5_2_verified_identity_crosswalk.csv")
    assert len(rows) == 80
    assert sum(1 for r in rows if r["verified_status"] == "IDENTITY_CONFIRMED") == 2
    assert sum(1 for r in rows if r["verified_status"] == "IDENTITY_CONFLICT") == 9
    assert sum(1 for r in rows if r["verified_status"] == "IDENTITY_PARTIAL") == 7
    assert sum(1 for r in rows if r["verified_status"] == "UNRESOLVED") == 62
    conflicts = {r["ticker"] for r in rows if r["verified_status"] == "IDENTITY_CONFLICT"}
    assert {"LB", "STI", "LLL", "HCP", "SE", "TE", "ALTR", "BEAM", "PLL"} == conflicts
    assert {r["ticker"] for r in rows if r["verified_status"] == "IDENTITY_CONFIRMED"} == {"BRK.B", "BF.B"}


def test_coverage_definitions_are_not_mixed():
    doc = (ROOT / "docs/research/P10_5_1_DATA_BASELINE_RECONCILIATION.md").read_text(encoding="utf-8")
    assert "1,095,490" in doc and "2,220,522" in doc
    assert "2,198" in doc and "4,429" in doc
    assert "1,160" in doc and "1,096" in doc
    assert "1,062" in doc and "918" in doc
    assert "95.16" in doc and "89.58" in doc
    assert "95%" in doc and "98%" in doc


def test_report_keeps_no_buy_and_limitations():
    doc = (ROOT / "docs/research/P10_5_2_BASELINE_IDENTITY_FINAL_AUDIT.md").read_text(encoding="utf-8")
    assert "NO_BUY" in doc
    assert "NO_PURCHASE: YES" in doc
    assert "P9_BASELINE: SNAPSHOT REPRODUCIBLE; TICKER POOL NOT_REPRODUCIBLE" in doc
    assert "ALL 8 NO-GO" in doc
    assert "24 new" in doc and "6 existing" in doc


def test_no_raw_vendor_files_committed():
    files = [p for p in DATA.glob("p10_5_2_*")]
    assert files
    assert all(p.suffix in {".csv", ".json"} for p in files)
    assert not list(DATA.glob("*.parquet"))
    assert not list(DATA.glob("*.pkl"))
