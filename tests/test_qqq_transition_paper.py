# -*- coding: utf-8 -*-
"""Tests for the independent QQQ TRANSITION web paper account."""
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from scripts.qqq_transition_paper import DataError, INITIAL_CAPITAL, run

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "research" / "qqq_transition_paper"


def _run(tmp_path):
    out = tmp_path / "ledger"
    dash = tmp_path / "dash.json"
    ledger, dashboard = run(DATA, out, dashboard_path=dash)
    return ledger, dashboard, out, dash


def test_complete_account_has_four_legs_and_25pct_sleeve(tmp_path):
    ledger, dashboard, out, dash = _run(tmp_path)
    assert ledger["initial_capital"] == INITIAL_CAPITAL
    assert ledger["sleeve_fraction"] == 0.25
    assert ledger["counts"]["trades"] == 32
    assert ledger["counts"]["fills"] == 128
    assert all(f["status"] == "SIMULATED" for f in ledger["fills"])
    assert all(f["execution_mode"] == "HISTORICAL_REPLAY" for f in ledger["fills"])
    assert {f["leg"] for f in ledger["fills"]} == {"SELL_BIL", "BUY_QQQ", "SELL_QQQ", "BUY_BIL"}
    assert (out / "daily_nav.csv").exists() and (out / "fills.csv").exists()
    assert dash.exists()


def test_five_spy_sessions_between_entry_and_exit(tmp_path):
    ledger, *_ = _run(tmp_path)
    spy = pd.read_csv(DATA / "SPY.csv")
    spy["Date"] = pd.to_datetime(spy["Date"], utc=True).dt.tz_convert(None).dt.normalize()
    cal = sorted(spy.Date.dt.date.unique())
    pairs = {}
    for f in ledger["fills"]:
        if f["leg"] == "BUY_QQQ":
            pairs.setdefault(f["trade_id"], {})["entry"] = pd.Timestamp(f["date"]).date()
        if f["leg"] == "SELL_QQQ":
            pairs.setdefault(f["trade_id"], {})["exit"] = pd.Timestamp(f["date"]).date()
    assert len(pairs) == 32
    for p in pairs.values():
        assert cal.index(p["exit"]) - cal.index(p["entry"]) == 5


def test_costs_are_ten_bps_per_leg_and_once(tmp_path):
    ledger, *_ = _run(tmp_path)
    assert ledger["cost_bps_per_leg"] == 10
    for f in ledger["fills"]:
        assert abs(f["cost"] - f["notional"] * 0.001) < 1e-6


def test_nav_and_account_consistent(tmp_path):
    ledger, dashboard, *_ = _run(tmp_path)
    last = ledger["daily"][-1]
    assert last["nav"] == pytest.approx(last["qqq_value"] + last["bil_value"])
    assert ledger["account"]["nav"] == pytest.approx(last["nav"])
    assert dashboard["initial_capital"] == 50000
    assert dashboard["max_drawdown"] < 0


def test_idempotent_rerun(tmp_path):
    a, *_ = _run(tmp_path)
    b, *_ = _run(tmp_path)
    assert a["fills"] == b["fills"]
    assert a["daily"] == b["daily"]
    assert a["account"] == b["account"]


def test_missing_or_invalid_price_fails_closed(tmp_path):
    bad = tmp_path / "data"
    shutil.copytree(DATA, bad)
    q = pd.read_csv(bad / "QQQ.csv")
    q.loc[0, "Adj Close"] = float("nan")
    q.to_csv(bad / "QQQ.csv", index=False)
    with pytest.raises(DataError):
        run(bad, tmp_path / "out", dashboard_path=tmp_path / "dash.json")


def test_dashboard_contract(tmp_path):
    _, dashboard, *_ = _run(tmp_path)
    for key in ("initial_capital", "nav", "return_pct", "cash", "qqq_units", "bil_units",
                "weight", "max_drawdown", "total_cost", "data_asof", "recent_fills",
                "recent_signals", "prospective_clock_started"):
        assert key in dashboard
    assert dashboard["prospective_clock_started"] is False
    assert dashboard["historical_replay"] is True


def test_dashboard_files_have_independent_panel():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "app.js").read_text(encoding="utf-8")
    assert 'id="qqqPaperSec"' in html
    assert "qqq_transition_paper.json" in js
    assert "SIMULATED" in html


def test_account_is_isolated_from_portfolio_50000(tmp_path):
    before = set((ROOT).glob("portfolio_50000_*"))
    _run(tmp_path)
    after = set((ROOT).glob("portfolio_50000_*"))
    assert before == after


def test_all_fills_use_share_quantity_not_dollars(tmp_path):
    ledger, *_ = _run(tmp_path)
    for f in ledger["fills"]:
        assert abs(f["notional"] - f["quantity"] * f["fill_price"]) < 1e-6
    by_trade = {}
    for f in ledger["fills"]:
        by_trade.setdefault(f["trade_id"], []).append(f)
    for legs in by_trade.values():
        legs = {f["leg"]: f for f in legs}
        assert legs["SELL_BIL"]["quantity"] > 10
        assert legs["BUY_QQQ"]["quantity"] > 1
        assert legs["SELL_QQQ"]["quantity"] > 1
        assert legs["BUY_BIL"]["quantity"] > 10


def test_legacy_before_fix_is_preserved_and_different(tmp_path):
    legacy = ROOT / "qqq_transition_paper" / "legacy_v1" / "fills.csv"
    assert legacy.exists()
    old = pd.read_csv(legacy)
    assert "quantity" in old.columns
    new, *_ = _run(tmp_path)
    assert new["counts"]["fills"] == 128
    # Old rows stored dollar notionals in quantity for three legs; new rows must not.
    first_old = old[old.trade_id == "T1"].iloc[0]
    first_new = [f for f in new["fills"] if f["trade_id"] == "T1"][0]
    assert abs(first_new["notional"] - first_new["quantity"] * first_new["fill_price"]) < 1e-6


def test_duplicate_conflicting_date_rejected(tmp_path):
    bad = tmp_path / "data"
    shutil.copytree(DATA, bad)
    q = pd.read_csv(bad / "QQQ.csv")
    q = pd.concat([q, q.tail(1)], ignore_index=True)
    q.to_csv(bad / "QQQ.csv", index=False)
    with pytest.raises(DataError):
        run(bad, tmp_path / "out", dashboard_path=tmp_path / "dash.json")


def test_missing_session_rejected(tmp_path):
    bad = tmp_path / "data"
    shutil.copytree(DATA, bad)
    q = pd.read_csv(bad / "QQQ.csv")
    drop_date = q.loc[q["Date"] > "2020-01-01", "Date"].iloc[0]
    q = q[q["Date"] != drop_date]
    q.to_csv(bad / "QQQ.csv", index=False)
    with pytest.raises(DataError):
        run(bad, tmp_path / "out", dashboard_path=tmp_path / "dash.json")
