#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""portfolio_50000.py 账本口径测试（P0 实际执行日 / P1 迟到推荐上界）。

为什么独立新建：`tests/test_portfolio_50000.py` 是**脚本式**测试（末尾 `sys.exit(0)`，
由 `tests/test_script_runner.py` 以子进程运行），无法在其内部追加 pytest 函数。

背景（10-13 事件）：
  · 10-08 的推荐在 10-13 仍 Active 时被追买 → 用**推荐日价格**建仓（P1 修）；
  · 买入流水把 `Date` 写成**推荐日**，而 `run()` 按 `Date` 排序回填 Cash_After
    → 出现 -9261.68 的"假超支"（P0 修：改用实际执行日；卖出侧早已用 exit_date）。
"""
import importlib.util
import sys
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


pf = _load("pf_ledger", REPO / "portfolio_50000.py")


def _rec(ticker, rec_date, price=100.0, status="Active"):
    return {
        "Recommendation_ID": pf.rec_id_of(ticker, rec_date, pf.CORE_TAG),
        "Ticker": ticker, "Rec_Date": rec_date, "Tag": pf.CORE_TAG,
        "Price": Decimal(str(price)), "Status": status,
        "Exit_Date": "", "Exit_Price": None, "Stop_Loss": Decimal("90.00"),
    }


def _recs(*recs):
    return {r["Recommendation_ID"]: r for r in recs}


def _run(recs, today, positions=None, transactions=None, start="2026-10-06", offline=True):
    """默认 offline=True → 不触网（走推荐日价），保证测试确定性。

    价格相关的测试显式传 offline=False 并 monkeypatch `pf._exec_price_for`。
    """
    positions = [] if positions is None else positions
    transactions = [] if transactions is None else transactions
    log = pf.process_buys(positions, transactions, recs, {"start_date": start}, today,
                          offline=offline)
    return positions, transactions, log


# --------------------------------------------------------------------------- #
# P0：实际执行日
# --------------------------------------------------------------------------- #
def test_transaction_date_uses_execution_day():
    """买入流水 Date 必须是【执行日】，不再是推荐日（推荐日保留在 Scan_Date/RecID 里）。"""
    _pos, txn, log = _run(_recs(_rec("CME", "2026-10-12", 270.75)), "2026-10-13")
    assert len(txn) == 1, log
    assert txn[0]["Date"] == "2026-10-13"          # 执行日
    assert txn[0]["Date"] != "2026-10-12"          # 不再是推荐日
    assert txn[0]["Scan_Date"] == "2026-10-12"     # 审计：推荐日仍在
    assert "2026-10-12" in txn[0]["Recommendation_ID"]
    assert txn[0]["Txn_ID"].endswith("|BUY")       # 幂等键不变


def test_entry_date_uses_execution_day():
    """持仓 Entry_Date 同样是执行日（否则与 history 快照错位）。"""
    pos, _txn, log = _run(_recs(_rec("EBAY", "2026-10-12", 108.19)), "2026-10-13")
    assert len(pos) == 1, log
    assert pos[0]["Entry_Date"] == "2026-10-13"
    assert "2026-10-12" in pos[0]["Recommendation_ID"]   # 推荐日可追溯


# --------------------------------------------------------------------------- #
# P1：迟到推荐上界（MAX_REC_AGE_DAYS = 2）
# --------------------------------------------------------------------------- #
def test_max_rec_age_constant_exists():
    assert pf.MAX_REC_AGE_DAYS == 2


def test_stale_recommendation_rejected():
    """today-3 天的 Active 推荐 → 不再追买（10-13 事件的正解）。"""
    _pos, txn, log = _run(_recs(_rec("CME", "2026-10-10", 270.75)), "2026-10-13")
    assert txn == [], log
    assert any("时效" in line for line in log), log


def test_fresh_recommendation_accepted():
    """边界包含：today-2 天（= cutoff）仍应接受。"""
    _pos, txn, log = _run(_recs(_rec("CME", "2026-10-11", 270.75)), "2026-10-13")
    assert len(txn) == 1, log
    assert txn[0]["Date"] == "2026-10-13"


def test_today_recommendation_accepted():
    _pos, txn, log = _run(_recs(_rec("CME", "2026-10-13", 270.75)), "2026-10-13")
    assert len(txn) == 1, log


def test_future_dated_recommendation_rejected():
    """未来日期（> today）不得买入（防御性上界）。"""
    _pos, txn, log = _run(_recs(_rec("CME", "2026-10-20", 270.75)), "2026-10-13")
    assert txn == [], log


# --------------------------------------------------------------------------- #
# P3：现金检查前移（真因标签正确）
# --------------------------------------------------------------------------- #
def test_cash_check_before_alloc_check():
    """现金远低于 1 Unit → 日志应报【现金不足】（前移前会被 80% 规则抢先报"占比"）。

    注：两种情形**都会被跳过**（决策集合不变），前移只让"真因"标签更准。
    """
    prior_txn = [{"Date": "2026-10-06", "Action": "BUY", "Amount": "49000.00",
                  "Txn_ID": "XXX|2026-10-06|Core_Dragon|BUY", "Ticker": "XXX"}]
    open_pos = [{"Ticker": "XXX", "Status": "OPEN", "Market_Value": "49000.00",
                 "Unit_ID": "U001", "Shares": "100"}]
    _pos, _txn, log = _run(_recs(_rec("CME", "2026-10-13", 270.75)), "2026-10-13",
                           positions=open_pos, transactions=prior_txn)
    assert not any("🛒" in line for line in log), log      # 依然买不进
    assert any("现金不足" in line for line in log), log      # ← 新标签
    assert not any("80%" in line for line in log), log


def test_alloc_label_still_used_when_cash_is_ample():
    """反向对照：现金充足但总股票将超 80% → 仍应报【占比约束】（前移没把标签一律改掉）。

    口径：derive_cash 自 50,000 起算 → 先用 20,000 ⇒ 现金 30,000；
    OPEN 市值 71,000 ⇒ equity 101,000；new_size 10,000
    → s+n = 81,000 > 0.8e = 80,800 ⇒ 占比拦截（而现金 30,000 ≥ 9,747 不会触发"现金不足"）。
    """
    prior_txn = [{"Date": "2026-10-06", "Action": "BUY", "Amount": "20000.00",
                  "Txn_ID": "XXX|2026-10-06|Core_Dragon|BUY", "Ticker": "XXX"}]
    open_pos = [{"Ticker": "XXX", "Status": "OPEN", "Market_Value": "71000.00",
                 "Unit_ID": "U001", "Shares": "100"}]
    _pos, _txn, log = _run(_recs(_rec("CME", "2026-10-13", 270.75)), "2026-10-13",
                           positions=open_pos, transactions=prior_txn)
    assert not any("🛒" in line for line in log), log
    assert any("80%" in line for line in log), log
    assert not any("现金不足" in line for line in log), log


# --------------------------------------------------------------------------- #
# P2：成交价用执行日市价（消除"假浮盈"的产生源）
# --------------------------------------------------------------------------- #
def test_buy_price_uses_execution_day_market_price(monkeypatch):
    """rec 价 100、执行日市价 105 → Entry_Price 必须是 105（不再是 100）。"""
    monkeypatch.setattr(pf, "_exec_price_for", lambda t: Decimal("105"))
    pos, txn, log = _run(_recs(_rec("CME", "2026-10-13", 100)), "2026-10-13",
                         offline=False)
    assert len(pos) == 1, log
    assert pos[0]["Entry_Price"] == "105.00"          # ← 执行日市价
    assert txn[0]["Price"] == "105.00"
    assert pos[0]["Cost_Basis"] == "9975.00"          # 95 股 × 105（Cost_Basis 在持仓行）
    assert not any("未取到执行日市价" in line for line in log), log


def test_buy_price_falls_back_to_rec_price_on_fetch_failure(monkeypatch):
    """取价失败 → 退回推荐日价并告警（保守，绝不编造价格）。"""
    monkeypatch.setattr(pf, "_exec_price_for", lambda t: None)
    pos, txn, log = _run(_recs(_rec("CME", "2026-10-13", 100)), "2026-10-13",
                         offline=False)
    assert len(pos) == 1, log
    assert pos[0]["Entry_Price"] == "100.00"          # ← 退回推荐日价
    assert txn[0]["Price"] == "100.00"
    assert any("未取到执行日市价" in line for line in log), log


def test_buy_price_offline_never_fetches(monkeypatch):
    """offline=True 时**不得**调用取价（monkeypatch 成抛错来证明真的没调）。"""
    def _boom(_t):
        raise AssertionError("offline 模式不应调用取价函数")

    monkeypatch.setattr(pf, "_exec_price_for", _boom)
    pos, _txn, log = _run(_recs(_rec("CME", "2026-10-13", 100)), "2026-10-13",
                          offline=True)
    assert len(pos) == 1, log
    assert pos[0]["Entry_Price"] == "100.00"
    assert any("（offline）" in line for line in log), log


# --------------------------------------------------------------------------- #
# 资金守护回归（原始疑点：现金不足时绝不能成交）
# --------------------------------------------------------------------------- #
def test_real_10_13_shape_never_overspends():
    """复刻 10-13 真实形态：同 run 先卖（释放现金）再买 → 两笔都成交且总额 ≤ 现金。

    现金 30,267.10；CME 9,747.00 + EBAY 9,953.48 = 19,700.48 ≤ 30,267.10 ✓
    （这是对"账户超支"疑点的正解：不存在透支，负 Cash_After 是排序假象。）
    """
    prior = [  # 10-07 四笔买入（合计 39,561.20）+ 10-13 两笔卖出（合计 19,828.30）
        {"Date": "2026-10-07", "Action": "BUY", "Amount": "39561.20",
         "Txn_ID": "OLD|2026-10-07|Core_Dragon|BUY", "Ticker": "OLD"},
        {"Date": "2026-10-13", "Action": "SELL", "Amount": "9634.06",
         "Txn_ID": "ANET|2026-10-07|Core_Dragon|SELL|2026-10-13", "Ticker": "ANET"},
        {"Date": "2026-10-13", "Action": "SELL", "Amount": "10194.24",
         "Txn_ID": "KR|2026-10-07|Core_Dragon|SELL|2026-10-13", "Ticker": "KR"},
    ]
    open_pos = [
        {"Ticker": "ADSK", "Status": "OPEN", "Market_Value": "9908.49",
         "Unit_ID": "U001", "Shares": "43"},
        {"Ticker": "ISRG", "Status": "OPEN", "Market_Value": "10129.44",
         "Unit_ID": "U003", "Shares": "24"},
    ]
    cash_before = pf.derive_cash(prior)
    assert cash_before == Decimal("30267.10")             # 卖出后可用现金
    _pos, txn, log = _run(
        _recs(_rec("CME", "2026-10-13", 270.75), _rec("EBAY", "2026-10-13", 108.19)),
        "2026-10-13", positions=open_pos, transactions=prior)

    new_buys = [t for t in txn if t["Txn_ID"].startswith(("CME", "EBAY"))]
    assert len(new_buys) == 2, log                        # 两笔都成交
    spent = sum(Decimal(t["Amount"]) for t in new_buys)
    assert spent == Decimal("19700.48"), spent
    assert spent <= cash_before, (spent, cash_before)     # ★ 绝不超支
    assert all(t["Date"] == "2026-10-13" for t in new_buys)   # P0：执行日
    assert pf.derive_cash(txn) == cash_before - spent     # 现金仍为正


def test_cash_sufficient_allows_buy():
    """反向对照：现金够时正常成交（避免上一条因别的原因通过而假绿）。"""
    prior_txn = [{"Date": "2026-10-06", "Action": "BUY", "Amount": "30000.00",
                  "Txn_ID": "XXX|2026-10-06|Core_Dragon|BUY", "Ticker": "XXX"}]
    open_pos = [{"Ticker": "XXX", "Status": "OPEN", "Market_Value": "30000.00",
                 "Unit_ID": "U001", "Shares": "100"}]
    _pos, txn, log = _run(_recs(_rec("CME", "2026-10-13", 270.75)), "2026-10-13",
                          positions=open_pos, transactions=prior_txn)
    new_buys = [t for t in txn if t["Txn_ID"].startswith("CME")]
    assert len(new_buys) == 1, log
    assert not any("⏸" in line for line in log), log
