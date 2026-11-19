import json
from pathlib import Path

import pandas as pd


def test_p390_98_rows_and_54_overlap():
    s = json.loads(Path("data/research/p17_1/p17_1_summary.json").read_text())
    assert s["p390"]["source_rows"] == 98
    assert s["p390"]["overlap_tickers"] == 54
    assert s["p390"]["overlap_high"] == 53
    assert s["p390"]["overlap_medium"] == 1


def test_p390_member_days_and_day_missing():
    s = json.loads(Path("data/research/p17_1/p17_1_summary.json").read_text())["p390"]
    assert s["high_expected_member_days"] == 38108
    assert s["medium_expected_member_days"] == 840
    assert s["high_observed_member_days"] == 37850
    assert s["medium_observed_member_days"] == 840
    d = pd.read_csv("data/research/p17_1/p17_1_p390_identity_reconciliation.csv")
    day = d[d.ticker == "DAY"].iloc[0]
    assert day.observed_member_days == 0


def test_frc_remains_medium():
    d = pd.read_csv("data/research/p17_1/p17_1_p390_identity_reconciliation.csv")
    assert d[d.ticker == "FRC"].source_confidence.iloc[0] == "medium"
    assert d[d.ticker == "FRC"].reviewed_identity_status.iloc[0] == "CANDIDATE_MEDIUM"


def test_p10_confirmed_only_two():
    s = json.loads(Path("data/research/p17_1/p17_1_summary.json").read_text())
    assert s["p10_in_p13"] == 26
    assert s["p10_confirmed_in_p13"] == 2


def test_verified_price_intersection_zero():
    s = json.loads(Path("data/research/p17_1/p17_1_summary.json").read_text())["coverage_priced"]
    assert s["verified_price_tickers"] == 0
    assert s["candidate_price_tickers"] == 53
    assert s["exploratory_100_names_gate"] is False


def test_sec_dei_has_no_trading_symbol():
    a = pd.read_csv("data/research/p17_1/p17_1_sec_facts_full_audit.csv").iloc[0]
    assert not bool(a.has_trading_symbol)
    assert not bool(a.has_security_exchange)
    assert a.ciks == 5368 and a.metrics == 19


def test_ciks_are_strings_with_leading_zero():
    d = pd.read_csv("data/research/p17_1/p17_1_security_identity_intervals.csv", dtype={"cik": str})
    assert d.cik.str.len().eq(10).all()


def test_share_class_aliases_separate():
    d = pd.read_csv("data/research/p17_1/p17_1_security_class_aliases.csv")
    assert set(d[d.alias_group == "COG/CTRA"].ticker) == {"COG", "CTRA"}
    assert set(d[d.alias_group == "DISCA/DISCK/WBD"].ticker) == {"DISCA", "DISCK", "WBD"}


def test_manifest_hashes():
    import hashlib
    m = json.loads(Path("data/research/p17_1/p17_1_manifest.json").read_text())
    for name, meta in m["outputs"].items():
        p = Path("data/research/p17_1") / name
        assert p.exists() and p.stat().st_size == meta["bytes"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == meta["sha256"]


def test_no_alpha_or_backtest_side_effect():
    assert not Path("data/research/p17_1/p17_1_nav.csv").exists()
    assert not Path("data/research/p17_1/p17_1_trade_ledger.csv").exists()
