# -*- coding: utf-8 -*-
"""AI 目标持仓「计划 vs 实际」：只读对比，不改目标文件、不算盈亏。

规则（docs 见 build_portfolio 注释）：
  shares_delta         = 目标股数 − 实际持股
  entry_price_diff_pct = 实际入场价相对参考价的偏离（%）
  fill_status          = pending / partial / aligned / over / exit_pending

数据来源：target 行（portfolio_50000_target.csv）+ positions（OPEN 持仓）。
"""
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import dashboard_export as de  # noqa: E402


def _target(**kw):
    base = {"ticker": "AMT", "action": "BUY", "target_shares": 66,
            "ref_price": 188.97, "stop_loss": "$177.22",
            "stop_loss_price": 177.22, "scan_date": "2026-10-26"}
    base.update(kw)
    return base


def _pos(**kw):
    base = {"ticker": "AMT", "shares": 66, "entry_price": 188.28,
            "entry_date": "2026-10-26", "stop_loss": "176.78",
            "stop_loss_price": 176.78, "current_price": 188.28}
    base.update(kw)
    return base


def test_aligned():
    rows = de._augment_target_actuals([_target()], [_pos()])
    r = rows[0]
    assert r["fill_status"] == "aligned"
    assert r["actual_shares"] == 66
    assert r["shares_delta"] == 0
    assert r["actual_entry_price"] == 188.28
    assert r["actual_entry_date"] == "2026-10-26"
    assert r["actual_stop_loss_price"] == 176.78
    assert r["entry_price_diff_pct"] == -0.37


def test_partial_fill():
    r = de._augment_target_actuals([_target()], [_pos(shares=53)])[0]
    assert r["fill_status"] == "partial"
    assert r["shares_delta"] == 13          # 还差 13 股
    assert r["actual_shares"] == 53


def test_pending_when_no_position():
    r = de._augment_target_actuals([_target()], [])[0]
    assert r["fill_status"] == "pending"
    assert r["actual_shares"] == 0
    assert r["actual_entry_price"] is None
    assert r["actual_stop_loss_price"] is None
    assert r["entry_price_diff_pct"] is None


def test_over_allocated():
    r = de._augment_target_actuals([_target()], [_pos(shares=80)])[0]
    assert r["fill_status"] == "over"
    assert r["shares_delta"] == -14

    # HOLD 行同理：目标=当前持股（由 scan 写入），正常应为 aligned
    hold = de._augment_target_actuals(
        [_target(action="HOLD", target_shares=53)], [_pos(shares=53)])[0]
    assert hold["fill_status"] == "aligned"


def test_sell_rows():
    sell = _target(action="SELL", target_shares=0)
    assert de._augment_target_actuals([sell], [_pos()])[0]["fill_status"] == "exit_pending"
    assert de._augment_target_actuals([dict(sell)], [])[0]["fill_status"] == "aligned"


def test_missing_ref_price_keeps_diff_none():
    r = de._augment_target_actuals([_target(ref_price=None)], [_pos()])[0]
    assert r["entry_price_diff_pct"] is None
