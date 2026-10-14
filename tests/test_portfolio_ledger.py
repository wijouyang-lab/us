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
import pytest
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


def _run(recs, today, positions=None, transactions=None, start="2026-10-06", offline=True,
         meta_extra=None):
    """默认 offline=True → 不触网（走推荐日价），保证测试确定性。

    价格相关的测试显式传 offline=False 并 monkeypatch `pf._exec_price_for`。
    meta_extra 用于注入 `exposure_target` 等字段（段 2）。
    """
    positions = [] if positions is None else positions
    transactions = [] if transactions is None else transactions
    meta = {"start_date": start}
    if meta_extra:
        meta.update(meta_extra)
    log = pf.process_buys(positions, transactions, recs, meta, today, offline=offline)
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


# --------------------------------------------------------------------------- #
# 段 2：动态仓位 —— meta.exposure_target（20%~80%，越界/非法回退 80%）
# --------------------------------------------------------------------------- #
def test_exposure_target_default_080():
    """meta 无该字段 / 为空 / meta=None → 一律按默认 0.80，且**不告警**。"""
    assert pf._exposure_target({}) == (Decimal("0.80"), None)
    assert pf._exposure_target(None) == (Decimal("0.80"), None)
    assert pf._exposure_target({"exposure_target": ""}) == (Decimal("0.80"), None)


def test_exposure_target_at_min_boundary():
    assert pf._exposure_target({"exposure_target": "0.20"}) == (Decimal("0.20"), None)


def test_exposure_target_at_max_boundary():
    assert pf._exposure_target({"exposure_target": "0.80"}) == (Decimal("0.80"), None)


def test_exposure_target_below_min_clamped():
    v, warn = pf._exposure_target({"exposure_target": "0.10"})
    assert v == Decimal("0.80"), v
    assert warn and "超出" in warn, warn


def test_exposure_target_above_max_clamped():
    v, warn = pf._exposure_target({"exposure_target": "0.95"})
    assert v == Decimal("0.80"), v
    assert warn and "超出" in warn, warn


def test_exposure_target_invalid_string():
    v, warn = pf._exposure_target({"exposure_target": "abc"})
    assert v == Decimal("0.80"), v
    assert warn and "非数字" in warn, warn


def test_ensure_meta_seeds_exposure_target(tmp_path):
    """新建 meta 必须带上 exposure_target（默认 0.80，字符串，与本文件金额字段同风格）。"""
    m = pf.ensure_meta(tmp_path, "2026-10-14")
    assert m["exposure_target"] == "0.80", m


def test_exposure_target_limits_buy():
    """同一持仓/同一推荐下：目标 0.30 拦、目标 0.80 放 —— 证明敞口真的在起作用。"""
    open_pos = [{"Ticker": "XXX", "Status": "OPEN", "Market_Value": "12500.00",
                 "Unit_ID": "U001", "Shares": "100"}]
    rec = _rec("CME", "2026-10-13", 100)
    eq = Decimal("62500")            # cash 50000（derive_cash）+ stock 12500
    ok30, why30 = pf._within_alloc(rec, open_pos, [], eq, Decimal("0.30"))
    assert ok30 is False and "30%" in why30, why30
    ok80, why80 = pf._within_alloc(rec, open_pos, [], eq, Decimal("0.80"))
    assert ok80 is True, why80


def test_exposure_target_040_allows_half_position():
    """target=0.40（半仓）→ 恰好允许 2 只各 20%，第 3 只被拦；并打印敞口日志。"""
    recs = _recs(_rec("AAA", "2026-10-13", 100),
                 _rec("BBB", "2026-10-13", 100),
                 _rec("CCC", "2026-10-13", 100))
    _pos, txn, log = _run(recs, "2026-10-13", meta_extra={"exposure_target": "0.40"})

    new_buys = [t for t in txn if t["Txn_ID"].split("|")[0] in ("AAA", "BBB", "CCC")]
    assert len(new_buys) == 2, (len(new_buys), log)          # 半仓 = 2 × 20%
    assert {t["Ticker"] for t in new_buys} == {"AAA", "BBB"}
    assert any("总股票将超 40%" in line for line in log), log
    assert any("当前敞口" in line and "目标 40.0%" in line for line in log), log


def test_exposure_target_default_allows_three():
    """反向对照：默认 0.80 → 同样的 3 只都能买（证明上一条的"2 只"是被 0.40 限制的）。"""
    recs = _recs(_rec("AAA", "2026-10-13", 100),
                 _rec("BBB", "2026-10-13", 100),
                 _rec("CCC", "2026-10-13", 100))
    _pos, txn, log = _run(recs, "2026-10-13")
    new_buys = [t for t in txn if t["Txn_ID"].split("|")[0] in ("AAA", "BBB", "CCC")]
    assert len(new_buys) == 3, (len(new_buys), log)


def test_exposure_target_clamp_warns_once_in_log():
    """越界值 → 回退 80% 并**在运行日志里告警一次**（同时仍能正常买入）。"""
    recs = _recs(_rec("AAA", "2026-10-13", 100))
    _pos, txn, log = _run(recs, "2026-10-13", meta_extra={"exposure_target": "0.05"})
    assert any("exposure_target" in line and "回退" in line for line in log), log
    assert any("当前敞口" in line and "目标 80.0%" in line for line in log), log
    assert len([t for t in txn if t["Txn_ID"].startswith("AAA")]) == 1, log


# --------------------------------------------------------------------------- #
# 日期铁律（层1 ISO 断言 / 层2 未来日期拒收 / 层3 幂等）
# --------------------------------------------------------------------------- #
def test_transaction_date_cannot_be_overridden(monkeypatch):
    """★ 买入的 Date / Entry_Date 只能来自 today，绝不被 Rec_Date 覆盖。"""
    recs = _recs(_rec("CME", "2026-10-13", 100))          # 推荐日 != 执行日
    pos, txn, log = _run(recs, "2026-10-14")              # 执行日
    assert len(txn) == 1, log
    assert txn[0]["Date"] == "2026-10-14"                  # 执行日，不是 10-13
    assert txn[0]["Date"] != "2026-10-13"
    assert pos[0]["Entry_Date"] == "2026-10-14"
    assert txn[0]["Scan_Date"] == "2026-10-13"             # 推荐日仍可追溯


@pytest.mark.parametrize("bad", ["", "2026-1-1", "2026/10/14", "2026-13-99",
                                 "2026-02-30", None, 20261014])
def test_reject_invalid_today_format(bad):
    """层 1：执行日必须是合法 ISO 日历日，否则写入路径立即失败。"""
    with pytest.raises(ValueError):
        pf._validate_today(bad)


def test_future_dated_transaction_skipped_on_load():
    """层 2：未来日期交易在加载时被剔除，且不参与现金推导。"""
    today = "2026-10-14"
    txns = [
        {"Txn_ID": "A|BUY", "Date": "2026-10-10", "Action": "BUY", "Amount": "1000.00"},
        {"Txn_ID": "B|BUY", "Date": "2026-10-20", "Action": "BUY", "Amount": "9999.00"},
        {"Txn_ID": "C|BUY", "Date": "", "Action": "BUY", "Amount": "1.00"},
    ]
    kept, warns = pf._reject_future_txns(txns, today)
    assert [t["Txn_ID"] for t in kept] == ["A|BUY", "C|BUY"]      # 未来那条被剔除
    assert warns and "未来日期" in warns[0] or "future" in warns[0].lower()
    # 现金推导只看保留列表：9999 的未来买入不得影响现金
    assert pf.derive_cash(kept) == pf.INITIAL_CAPITAL - Decimal("1001.00")


def test_sell_idempotency():
    """层 3：同一推荐 + 同一 Exit_Date 只产生一条 SELL（重复运行不重复卖）。"""
    rec = _rec("CME", "2026-10-07", 100)
    rec.update({"Status": "Stop_Loss_Hit", "Exit_Date": "2026-10-14",
                "Exit_Price": Decimal("90")})
    recs = {rec["Recommendation_ID"]: rec}
    positions = [{"Portfolio_ID": "US-50000-001", "Unit_ID": "U001", "Ticker": "CME",
                  "Shares": "10", "Entry_Price": "100", "Entry_Date": "2026-10-07",
                  "Status": "OPEN", "Recommendation_ID": rec["Recommendation_ID"]}]
    txns = []
    pf.process_sells(positions, txns, recs, "2026-10-14")
    first = len(txns)
    assert first == 1, txns
    pf.process_sells(positions, txns, recs, "2026-10-14")   # 再跑一次
    assert len(txns) == first, txns                          # 幂等：没有新增
    assert txns[0]["Txn_ID"].endswith("|SELL|2026-10-14")
