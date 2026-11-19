import json
from pathlib import Path

import pandas as pd


def test_identity_is_blocked():
    c = json.loads(Path("data/research/p17/p17_identity_coverage.json").read_text())
    assert c["status"] == "DATA_BLOCKED"
    assert c["verified_member_day_rate"] < 0.01
    assert c["mapped_tickers"] == 3


def test_identity_includes_unresolved_and_conflicts():
    d = pd.read_csv("data/research/p17/p17_security_identity.csv")
    assert set(d.status.unique()) >= {"UNRESOLVED", "IDENTITY_CONFLICT", "IDENTITY_CONFIRMED"}
    assert (d.status == "UNRESOLVED").sum() > 500


def test_sec_facts_have_pit_dates_but_are_not_joined():
    a = pd.read_csv("data/research/p17/p17_sec_facts_audit.csv").iloc[0]
    assert a["rows"] > 6_000_000
    assert a["null_pit"] == 0
    assert a["status"] == "AVAILABLE_BUT_IDENTITY_BLOCKED"


def test_p16_regime_window_counts_are_main_sample():
    a = json.loads(Path("data/research/p17/p16_engine_audit.json").read_text())
    assert a["main_days"] == 1258 and a["main_risk_on"] == 979
    assert a["three_days"] == 753 and a["three_risk_on"] == 533


def test_p16_audit_flags_mismatches():
    a = json.loads(Path("data/research/p17/p16_engine_audit.json").read_text())
    assert "raw MOM63" in a["ranking_issue"]
    assert "SPY close" in a["price_basis"]
    assert "excess return" in a["sharpe_issue"]


def test_no_fundamental_backtest_was_faked():
    s = json.loads(Path("data/research/p17/p17_summary.json").read_text())
    assert s["overall"] == "DATA_BLOCKED"
    assert s["entry"] == "NOT_RUN_IDENTITY_BLOCKED"
    assert s["exit"] == "NOT_RUN_IDENTITY_BLOCKED"
    assert s["portfolio"] == "NOT_RUN"


def test_manifest_hashes():
    import hashlib
    m = json.loads(Path("data/research/p17/p17_manifest.json").read_text())
    for name, meta in m["outputs"].items():
        p = Path("data/research/p17") / name
        assert p.exists() and p.stat().st_size == meta["bytes"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == meta["sha256"]


def test_no_trade_ledger_or_nav_claim():
    assert not Path("data/research/p17/p17_trade_ledger.csv").exists()
    assert not Path("data/research/p17/p17_nav.csv").exists()
