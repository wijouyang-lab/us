# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd
import pytest

from tools.paper_trading.account import (AccountState, AccountStore, apply_split,
                                         credit_dividend, position_shares)
from tools.paper_trading.engine import PaperEngine
from tools.paper_trading.valuation import mark_to_market, metrics


def buy(engine, cid="b1", shares=100, price=100.0, ticker="AAPL", strategy="VALUE"):
    p = engine.propose(client_order_id=cid, ticker=ticker, side="BUY", shares=shares,
                       reference_price=price, price_asof="2026-11-03T20:00:00Z",
                       strategy=strategy, slippage_bps=3)
    return engine.confirm(p["order_id"], p["confirm_token"])


def test_initial_account_is_exactly_50000(tmp_path):
    e = PaperEngine(tmp_path)
    a = e.account()
    assert a["initial_cash"] == 50000.0
    assert a["cash"] == 50000.0
    assert a["positions"] == []
    assert a["realized_pnl"] == 0.0


def test_buy_updates_cash_position_and_costs(tmp_path):
    e = PaperEngine(tmp_path); o = buy(e)
    a = e.account(); f = o["fill"]
    assert len(a["positions"]) == 1
    assert a["positions"][0]["shares"] == 100
    assert a["cash"] == pytest.approx(50000 - f["reference_price"] * f["shares"] - f["total_cost"])
    assert f["fill_price"] > f["reference_price"]
    assert f["total_cost"] == pytest.approx(f["commission"] + f["sec_fee"] + f["taf_fee"] +
                                            f["cat_fee"] + f["clearing_fee"] + f["exchange_fee"] +
                                            f["slippage"])


def test_duplicate_and_insufficient_cash_rejected(tmp_path):
    e = PaperEngine(tmp_path); buy(e)
    with pytest.raises(ValueError, match="duplicate"):
        buy(e)
    with pytest.raises(ValueError, match="insufficient"):
        e.propose(client_order_id="huge", ticker="MSFT", side="BUY", shares=100000,
                  reference_price=100, price_asof="2026-11-03", strategy="VALUE")


def test_partial_sell_realizes_pnl_and_blocks_short(tmp_path):
    e = PaperEngine(tmp_path); buy(e)
    p = e.propose(client_order_id="s1", ticker="AAPL", side="SELL", shares=40,
                  reference_price=110, price_asof="2026-11-04", strategy="VALUE")
    s = e.confirm(p["order_id"], p["confirm_token"])
    assert s["fill"]["fill_price"] < 110
    assert position_shares(e.store.load(), "AAPL") == 60
    with pytest.raises(ValueError, match="insufficient"):
        e.propose(client_order_id="s2", ticker="AAPL", side="SELL", shares=61,
                  reference_price=110, price_asof="2026-11-04", strategy="VALUE")


def test_cancel_pending_and_cannot_confirm(tmp_path):
    e = PaperEngine(tmp_path)
    p = e.propose(client_order_id="c1", ticker="AAPL", side="BUY", shares=10,
                  reference_price=100, price_asof="2026-11-03", strategy="VALUE")
    e.cancel(p["order_id"])
    with pytest.raises(ValueError, match="not pending"):
        e.confirm(p["order_id"], p["confirm_token"])


def test_expired_proposal_fails_closed(tmp_path):
    e = PaperEngine(tmp_path, max_proposal_age_seconds=0)
    p = e.propose(client_order_id="x", ticker="AAPL", side="BUY", shares=10,
                  reference_price=100, price_asof="2026-11-03", strategy="VALUE")
    with pytest.raises(ValueError):
        e.confirm(p["order_id"], p["confirm_token"])


def test_dividend_and_split_accounting(tmp_path):
    e = PaperEngine(tmp_path); buy(e, shares=100)
    st = e.store.load()
    d = credit_dividend(st, ticker="AAPL", amount_per_share=0.25, ex_date="2026-11-10", source="issuer")
    e.store.save(st); e.store.append_ledger(d)
    assert d["cash"] == pytest.approx(25.0)
    st = e.store.load(); sp = apply_split(st, ticker="AAPL", ratio=4, effective_date="2026-11-20")
    e.store.save(st); e.store.append_ledger(sp)
    assert position_shares(st, "AAPL") == 400


def test_nav_requires_prices_and_reconciles(tmp_path):
    e = PaperEngine(tmp_path); buy(e, shares=10, price=100)
    pos = e.account()["positions"][0]
    snap = mark_to_market(e.store.load(), {"AAPL": 120.0})
    assert snap["positions_value"] == pytest.approx(pos["shares"] * 120)
    assert snap["nav"] == pytest.approx(snap["cash"] + snap["positions_value"])
    with pytest.raises(ValueError, match="missing price"):
        mark_to_market(e.store.load(), {})


def test_metrics_from_nav_series():
    idx = pd.date_range("2026-01-01", periods=5, freq="B")
    nav = pd.Series([50000, 51000, 50500, 52000, 53000], index=idx)
    m = metrics(nav)
    assert m["status"] == "OK"
    assert m["max_drawdown"] < 0
    assert m["cagr"] > 0


def test_ledger_is_append_only_and_order_ids_unique(tmp_path):
    e = PaperEngine(tmp_path); buy(e, cid="b1"); buy(e, cid="b2", shares=1, ticker="MSFT")
    h = e.history()
    assert len(h) == 2
    assert h[0]["order_id"] != h[1]["order_id"]
    assert all(x["type"] == "FILL" for x in h)
