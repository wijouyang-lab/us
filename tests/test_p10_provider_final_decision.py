import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/research"


def test_final_decision_contains_frozen_counts():
    doc = (ROOT / "docs/research/P10_PROVIDER_TRACK_FINAL_DECISION.md").read_text(encoding="utf-8")
    for text in (
        "P9_TICKER_POOL: NOT_REPRODUCIBLE",
        "P9_TICKER_POOL_SIZE: 1160",
        "IDENTITY_CONFIRMED: 2 / 80",
        "IDENTITY_CONFLICT: 9 / 80",
        "IDENTITY_PARTIAL: 7 / 80",
        "IDENTITY_UNRESOLVED: 62 / 80",
        "FREE_RESEARCH_TICKER_COVERAGE: 93.69%",
        "LICENSE_CLEARED_PRODUCTION_COVERAGE: 0%",
        "PURCHASE_DECISION: NO_BUY",
        "PRODUCTION_DEPLOYMENT_READY: false",
        "ALL_P9_STRATEGIES: NO_GO",
    ):
        assert text in doc


def test_18_row_identity_file_is_exceptions_only():
    rows = list(csv.DictReader((DATA / "p10_5_3_historical_ticker_identity.csv").open(encoding="utf-8")))
    assert len(rows) == 18
    assert {r["identity_status"] for r in rows} == {
        "IDENTITY_CONFIRMED", "IDENTITY_CONFLICT", "IDENTITY_PARTIAL"
    }
    assert sum(1 for r in rows if r["identity_status"] == "IDENTITY_CONFLICT") == 9
    assert sum(1 for r in rows if r["identity_status"] == "IDENTITY_PARTIAL") == 7
    assert sum(1 for r in rows if r["identity_status"] == "IDENTITY_CONFIRMED") == 2
    doc = (ROOT / "docs/research/P10_PROVIDER_TRACK_FINAL_DECISION.md").read_text(encoding="utf-8")
    assert "2 / 887" in doc
    assert "not a full identity audit" in doc.lower()


def test_local_replay_was_executed_and_ci_was_not():
    r = json.loads((DATA / "p10_5_3_replay_result.json").read_text(encoding="utf-8"))
    assert r["all_expected_matched"] is True
    assert r["input_hashes_verified"] is True
    assert r["ci_replay"] is False
    assert r["snapshot_member_days"] == 1095490
    assert r["snapshot_valid"] == 986358
    assert r["daily_member_days"] == 2220522
    assert r["daily_valid"] == 2113080
    assert (ROOT / "tools/research/p10/replay_p9_baseline.py").exists()


def test_no_raw_data_in_public_repo():
    assert not list(DATA.glob("*.parquet"))
    assert not list(DATA.glob("*.pkl"))
    assert not list(DATA.glob("*.sqlite"))


def test_reconsideration_conditions_are_explicit():
    doc = (ROOT / "docs/research/P10_PROVIDER_TRACK_FINAL_DECISION.md").read_text(encoding="utf-8")
    assert "total cost ≤ $20" in doc
    assert "subscription ≤ one month" in doc
    assert "no VPS required" in doc
    assert "95% member-day and 98% ticker" in doc
