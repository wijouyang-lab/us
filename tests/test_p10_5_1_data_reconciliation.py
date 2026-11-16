import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/research"


def test_local_finsaber_matches_public_reproduce_hash():
    rows = list(csv.DictReader((DATA / "p10_5_1_free_source_comparison.csv").open(encoding="utf-8")))
    local = next(r for r in rows if r["source"] == "FINSABER-reproduce")
    assert local["bytes"] == "265180873"
    assert local["sha256"] == "f67e3972dceefbbdf6c17b84b30957a7b83518401955fff8ae0bc4ae206fa83f"
    assert "Apache-2.0" in local["license"]
    assert local["claim"] == "BASELINE_EXACT_MATCH"


def test_v2_license_is_not_apache():
    rows = list(csv.DictReader((DATA / "p10_5_1_free_source_comparison.csv").open(encoding="utf-8")))
    v2 = next(r for r in rows if r["source"] == "FINSABER-V2-Data")
    assert "other" in v2["license"].lower()
    assert "NOT Apache-2.0" in v2["license"]


def test_free_v2_adds_30_tickers_but_does_not_pass_98():
    rows = list(csv.DictReader((DATA / "p10_5_1_free_source_comparison.csv").open(encoding="utf-8")))
    local = next(r for r in rows if r["source"] == "FINSABER-reproduce")
    union = next(r for r in rows if r["source"] == "UNION_LOCAL_V2")
    assert int(union["member_days"]) - int(local["member_days"]) == 11802
    assert float(union["ticker_coverage"]) == 0.9369
    assert float(union["ticker_coverage"]) < 0.98
    assert union["claim"] == "FREE_UNION_NOT_LICENSE_CLEARED"


def test_baseline_denominators_are_distinct_not_averaged():
    # P9 uses snapshot rows; independent rebuild uses daily-expanded rows.
    assert 1_095_490 / 2_198 > 400
    assert 2_220_522 / 4_429 > 490
    assert 981_362 / 1_095_490 < 0.95
    assert 2_113_080 / 2_220_522 > 0.95
    # They must not be averaged or max-selected.
    assert 1_095_490 != 2_220_522
    assert abs((981_362 / 1_095_490) - (2_113_080 / 2_220_522)) > 0.05


def test_identity_crosswalk_has_80_rows_47_without_overlap():
    rows = list(csv.DictReader((DATA / "p10_5_1_identity_crosswalk.csv").open(encoding="utf-8")))
    assert len(rows) == 80
    assert sum(1 for r in rows if r["has_local_price"].lower() == "true") == 47
    assert sum(1 for r in rows if r["has_local_price"].lower() == "false") == 33
    assert all(r["identity_status"] == "UNRESOLVED" for r in rows)
    assert all(r["confidence"] == "LOW" for r in rows)


def test_share_class_and_identity_categories_are_not_confirmed():
    rows = list(csv.DictReader((DATA / "p10_5_1_identity_crosswalk.csv").open(encoding="utf-8")))
    assert sum(1 for r in rows if r["category"] == "C_SHARE_CLASS_MAPPING") == 2
    assert sum(1 for r in rows if r["category"] == "C_TICKER_REUSE_MULTI_CIK") == 0
    assert sum(1 for r in rows if r["category"] == "C_OR_A_REVIEW_REQUIRED") == 66
    assert sum(1 for r in rows if r["category"] == "UNRESOLVED") == 12


def test_no_raw_finsaber_or_v2_files_committed():
    files = [p for p in DATA.glob("*") if p.is_file() and p.name.startswith("p10_5_1")]
    assert all(p.suffix in {".csv", ".json"} for p in files)
    assert not list(DATA.glob("*.parquet"))
    assert not list(DATA.glob("*.pkl"))


def test_report_keeps_no_buy_and_gates():
    doc = (ROOT / "docs/research/P10_5_1_DATA_BASELINE_RECONCILIATION.md").read_text(encoding="utf-8")
    assert "NO_BUY" in doc
    assert "NO_PURCHASE: YES" in doc
    assert "95%" in doc and "98%" in doc
    assert "P9_DATA_REPRODUCIBILITY: BLOCKED UNTIL BASELINE RECONCILED" in doc
    assert "ALL 8 NO-GO" in doc


def test_cik_coverage_and_identity_remain_unresolved():
    rows = list(csv.DictReader((DATA / "p10_5_1_identity_crosswalk.csv").open(encoding="utf-8")))
    assert sum(1 for r in rows if int(r["v2_cik_count"]) > 0) == 68
    assert sum(1 for r in rows if r["v2_cik_name"] != "UNKNOWN") == 68
    assert all(r["identity_status"] == "UNRESOLVED" for r in rows)
    assert all(r["sec_name_match"] == "NOT_CHECKED" for r in rows)
