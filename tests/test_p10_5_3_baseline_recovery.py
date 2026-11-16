import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/research"


def _rows(name):
    return list(csv.DictReader((DATA / name).open(encoding="utf-8")))


def test_baseline_manifest_marks_1160_not_reproducible():
    rows = {r["artifact"]: r for r in _rows("p10_5_3_baseline_reconstruction_manifest.csv")}
    assert rows["P9_TICKER_POOL_1160"]["reconstruction_status"] == "NOT_REPRODUCIBLE"
    assert rows["P9_TICKER_POOL_1160"]["sha256"] == "UNKNOWN"
    assert rows["P9_SNAPSHOT_DENOMINATOR"]["reconstruction_status"] == "REPRODUCIBLE"
    assert rows["P9_SNAPSHOT_DENOMINATOR"]["rows"] == "2198"
    assert rows["P9_DAILY_DENOMINATOR"]["rows"] == "4429"
    assert rows["P9_SNAPSHOT_DENOMINATOR"]["sha256"].startswith("646b2e47")


def test_source_hashes_are_recorded_not_raw_files():
    rows = {r["file"]: r for r in _rows("p10_5_2_source_manifest.csv")}
    assert rows["finsaber_prices_raw.csv"]["sha256"] == "f67e3972dceefbbdf6c17b84b30957a7b83518401955fff8ae0bc4ae206fa83f"
    assert rows["finsaber_prices_raw.csv"]["rows"] == "4736109"
    assert rows["pit_coverage_by_ticker.csv"]["rows"] == "1062"
    assert not list(DATA.glob("*.parquet"))


def test_1160_is_not_substituted_with_1096_or_887():
    doc = (ROOT / "docs/research/P10_5_3_P9_TICKER_POOL_RECOVERY.md").read_text(encoding="utf-8")
    assert "P9_TICKER_POOL: NOT_REPRODUCIBLE" in doc
    assert "1,160" in doc
    assert "1,096" in doc and "887" in doc
    assert "1,062" in doc and "918" in doc


def test_identity_crosswalk_has_9_conflicts_7_partial_2_confirmed():
    rows = _rows("p10_5_3_historical_ticker_identity.csv")
    assert len(rows) == 18
    conflicts = {r["ticker"] for r in rows if r["identity_status"] == "IDENTITY_CONFLICT"}
    assert conflicts == {"LB", "STI", "LLL", "HCP", "SE", "TE", "ALTR", "BEAM", "PLL"}
    partial = {r["ticker"] for r in rows if r["identity_status"] == "IDENTITY_PARTIAL"}
    assert partial == {"CA", "EMC", "DTV", "DO", "SHLD", "WYND", "DNB"}
    confirmed = {r["ticker"] for r in rows if r["identity_status"] == "IDENTITY_CONFIRMED"}
    assert confirmed == {"BRK.B", "BF.B"}


def test_share_class_mapping_is_explicit_and_not_issuer_only():
    rows = {r["ticker"]: r for r in _rows("p10_5_3_historical_ticker_identity.csv")}
    assert rows["BRK.B"]["old_cik"] == "1067983"
    assert "BRK-B" in rows["BRK.B"]["provider_alias"]
    assert rows["BF.B"]["old_cik"] == "14693"
    assert "BFB" in rows["BF.B"]["provider_alias"]
    assert "BF-B" in rows["BF.B"]["provider_alias"]


def test_v2_diff_has_dual_status_and_does_not_claim_unresolved_as_confirmed():
    rows = _rows("p10_5_2_v2_incremental_ticker_diff.csv")
    assert len(rows) == 30
    assert sum(1 for r in rows if r["change_type"] == "NEW_COVERAGE") == 24
    assert sum(1 for r in rows if r["change_type"] == "EXISTING_ADDED") == 6
    assert sum(int(r["added_member_days"]) for r in rows) == 11802
    assert all(r["identity_status_at_join"] == "UNRESOLVED" for r in rows)
    confirmed = {r["ticker"] for r in rows if r["identity_status_after_review"] == "IDENTITY_CONFIRMED"}
    assert confirmed == {"BRK.B", "BF.B"}


def test_production_coverage_is_not_misstated():
    doc = (ROOT / "docs/research/P10_5_3_P9_TICKER_POOL_RECOVERY.md").read_text(encoding="utf-8")
    assert "IDENTITY_CONFIRMED_TICKER_COVERAGE: 0.23%" in doc
    assert "LICENSE_CLEARED_PRODUCTION_COVERAGE: 0%" in doc
    assert "93.69%" in doc
    assert "ALL 8 NO-GO" in doc
    assert "NO_BUY" in doc
