# -*- coding: utf-8 -*-
"""$50,000 Long-Term Portfolio 回归测试。

覆盖：初始化幂等、BUY/HOLD/SELL 规则、Entry Price 固定、
      Realized / Unrealized PnL、Cash / Equity 推导、历史快照幂等、
      以及 Dashboard 导出字段与两位小数格式。

运行：python3.11 tests/test_portfolio_50000.py
"""

import csv
import importlib.util
import json
import shutil
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  {'[PASS]' if ok else '[FAIL]'} {name}" + (f"  {detail}" if detail else ""))
    return ok


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


pf = _load("pfmod", REPO / "portfolio_50000.py")

TH_COLS = ["Date", "Ticker", "Name", "Tag", "Score", "Price", "Stop_Loss",
           "Exit_Date", "Exit_Price", "Status", "Close_Price"]


def mk_fixture(recs, start_date=None):
    d = Path(tempfile.mkdtemp(prefix="pf_"))
    with open(d / "trade_history.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TH_COLS)
        w.writeheader()
        for r in recs:
            row = {c: "" for c in TH_COLS}
            row.update(r)
            w.writerow(row)
    if start_date:
        (d / "portfolio_50000_meta.json").write_text(json.dumps({
            "portfolio_id": "US-50000-001",
            "initial_capital": "50000.00",
            "start_date": start_date,
            "unit_dollars": "10000.00",
            "max_open_positions": 4,
            "currency": "USD",
        }), encoding="utf-8")
    return d


def run_pf(d, prices=None):
    if prices is not None:
        # 适配 fetch_last_closes 的新返回结构：{TICKER: {"current": Decimal, ...}}
        pf.fetch_last_closes = lambda tickers: {k.upper(): {"current": v} for k, v in prices.items()}
    return pf.run(d, offline=False)


def read_csv(d, name):
    p = d / name
    if not p.exists():
        return []
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def core(ticker, date, price, status="Active", exit_date="", exit_price="", tag="Core_Dragon"):
    return dict(Date=date, Ticker=ticker, Name=ticker, Tag=tag, Score="80", Price=price,
                Stop_Loss="0", Exit_Date=exit_date, Exit_Price=exit_price, Status=status,
                Close_Price=price)


print("=" * 70)
print("$50,000 Long-Term Portfolio 回归测试")
print("=" * 70)

TODAY = pf.us_today_str()

# ---------------------------------------------------------------- 1-2 初始化
print("\n--- 初始化与幂等 ---")
d = mk_fixture([core("AMD", TODAY, "630.48")])
r1 = run_pf(d, prices={"AMD": Decimal("630.48")})
meta = json.loads((d / "portfolio_50000_meta.json").read_text(encoding="utf-8"))
check("1. Initial Capital = 50000", Decimal(meta["initial_capital"]) == Decimal("50000.00"),
      meta["initial_capital"])
check("1b. Portfolio_ID = US-50000-001", meta["portfolio_id"] == "US-50000-001")

r2 = run_pf(d, prices={"AMD": Decimal("630.48")})
meta2 = json.loads((d / "portfolio_50000_meta.json").read_text(encoding="utf-8"))
check("2. 第二次运行不重新初始化（start_date 不变）",
      meta2["start_date"] == meta["start_date"], meta2["start_date"])

# ---------------------------------------------------------------- 3-5 BUY / Entry
print("\n--- BUY 与 Entry Price ---")
pos = read_csv(d, "portfolio_50000_positions.csv")
openp = [p for p in pos if p["Status"] == "OPEN"]
check("3. BUY 创建 Position", len(openp) == 1, f"{len(openp)} 个")
amd = openp[0]
check("3b. Shares = floor(10000 / 630.48) = 15", int(amd["Shares"]) == 15, amd["Shares"])
check("3c. 投入不超过 $10,000", Decimal(amd["Cost_Basis"]) <= Decimal("10000.00"), amd["Cost_Basis"])
check("3d. Unit_ID 已分配", amd["Unit_ID"] in ("U001", "U002", "U003", "U004"), amd["Unit_ID"])
check("4. Entry_Price 固定为推荐日 Open", Decimal(amd["Entry_Price"]) == Decimal("630.48"),
      amd["Entry_Price"])

# 改价后重跑，Entry 必须不动
run_pf(d, prices={"AMD": Decimal("700.00")})
pos2 = read_csv(d, "portfolio_50000_positions.csv")
amd2 = [p for p in pos2 if p["Ticker"] == "AMD"][0]
check("5. 当前价变化不改变 Entry_Price", Decimal(amd2["Entry_Price"]) == Decimal("630.48"),
      f"entry={amd2['Entry_Price']} current={amd2['Current_Price']}")
check("5b. Current_Price 已更新", Decimal(amd2["Current_Price"]) == Decimal("700.00"))

# ---------------------------------------------------------------- 6-7 Unrealized
print("\n--- Unrealized PnL ---")
r = run_pf(d, prices={"AMD": Decimal("700.00")})
upl = Decimal(amd2["Shares"]) * (Decimal("700.00") - Decimal("630.48"))
check("6. Unrealized PnL 为正且正确",
      Decimal([p for p in read_csv(d, "portfolio_50000_positions.csv")
               if p["Ticker"] == "AMD"][0]["Unrealized_PnL"]) == upl.quantize(Decimal("0.01")),
      str(upl))
run_pf(d, prices={"AMD": Decimal("600.00")})
p3 = [p for p in read_csv(d, "portfolio_50000_positions.csv") if p["Ticker"] == "AMD"][0]
neg = Decimal("15") * (Decimal("600.00") - Decimal("630.48"))
check("7. Unrealized PnL 为负且正确", Decimal(p3["Unrealized_PnL"]) == neg.quantize(Decimal("0.01")),
      p3["Unrealized_PnL"])

# ---------------------------------------------------------------- 8-10 SELL
print("\n--- SELL / Realized PnL ---")
d2 = mk_fixture([core("AMD", TODAY, "630.48"), core("META", TODAY, "700.00")])
run_pf(d2, prices={"AMD": Decimal("630.48"), "META": Decimal("700.00")})
# Review 裁决止损退出
with open(d2 / "trade_history.csv", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
for row in rows:
    if row["Ticker"] == "AMD":
        row["Status"] = "Stop_Loss_Hit"
        row["Exit_Date"] = TODAY
        row["Exit_Price"] = "590.00"
with open(d2 / "trade_history.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=TH_COLS); w.writeheader()
    for row in rows: w.writerow(row)

res = run_pf(d2, prices={"META": Decimal("700.00")})
txns = read_csv(d2, "portfolio_50000_transactions.csv")
sell = [t for t in txns if t["Action"] == "SELL"]
check("8. SELL 产生交易记录", len(sell) == 1, f"{len(sell)} 条")
realized = Decimal("15") * (Decimal("590.00") - Decimal("630.48"))
check("8b. Realized PnL 正确", len(sell) == 1 and Decimal(sell[0]["Realized_PnL"]) == realized.quantize(Decimal("0.01")),
      sell[0]["Realized_PnL"] if sell else "-")
cash_expected = Decimal("50000.00") - Decimal("9457.20") - Decimal("9800.00") + Decimal("15") * Decimal("590.00")
check("9. SELL 后 Cash 正确", res["cash"] == cash_expected.quantize(Decimal("0.01")),
      f"{res['cash']} vs {cash_expected}")
p4 = [p for p in read_csv(d2, "portfolio_50000_positions.csv") if p["Ticker"] == "AMD"][0]
check("10. SELL 后 Position 清零", p4["Shares"] == "0" and p4["Status"] == "CLOSED",
      f"shares={p4['Shares']} status={p4['Status']}")

# ---------------------------------------------------------------- 11-12 防重复 / Observation
print("\n--- 防重复买入 / Observation 隔离 ---")
before = len(read_csv(d2, "portfolio_50000_transactions.csv"))
run_pf(d2, prices={"META": Decimal("700.00")})
run_pf(d2, prices={"META": Decimal("700.00")})
after = len(read_csv(d2, "portfolio_50000_transactions.csv"))
check("11. 已持有再 BUY 不重复买入（HOLD）", before == after, f"{before} -> {after}")

d3 = mk_fixture([core("OBS1", TODAY, "50.00", tag="Observation"),
                 core("AMD", TODAY, "630.48")])
run_pf(d3, prices={"AMD": Decimal("630.48")})
tk = [p["Ticker"] for p in read_csv(d3, "portfolio_50000_positions.csv")]
check("12. Observation 不进入 Portfolio", "OBS1" not in tk and "AMD" in tk, str(tk))

# ---------------------------------------------------------------- 13-16 Cash/Equity/PnL/Return
print("\n--- Cash / Equity / PnL / Return ---")
d4 = mk_fixture([core("AMD", TODAY, "630.48"), core("META", TODAY, "700.00")])
r4 = run_pf(d4, prices={"AMD": Decimal("630.48"), "META": Decimal("700.00")})
exp_cash = Decimal("50000.00") - Decimal("9457.20") - Decimal("9800.00")
check("13. Cash 由流水推导正确", r4["cash"] == exp_cash.quantize(Decimal("0.01")),
      f"{r4['cash']} vs {exp_cash}")
check("14. Total Equity = Cash + Stock Value",
      r4["total_equity"] == (r4["cash"] + r4["stock_value"]).quantize(Decimal("0.01")),
      str(r4["total_equity"]))
r4b = run_pf(d4, prices={"AMD": Decimal("700.00"), "META": Decimal("700.00")})
exp_pnl = Decimal("15") * (Decimal("700.00") - Decimal("630.48"))
check("15. Total PnL = Realized + Unrealized",
      r4b["total_pnl"] == (r4b["realized_pnl"] + r4b["unrealized_pnl"]).quantize(Decimal("0.01"))
      and r4b["total_pnl"] == exp_pnl.quantize(Decimal("0.01")), str(r4b["total_pnl"]))
check("16. Return% = Total PnL / 50000（分母恒为初始本金）",
      r4b["return_pct"] == (exp_pnl / Decimal("50000.00") * 100).quantize(Decimal("0.01")),
      f"{r4b['return_pct']}%")

# ---------------------------------------------------------------- 17-20 幂等
print("\n--- History 快照幂等 / 永不重置 ---")
hist = read_csv(d4, "portfolio_50000_history.csv")
check("17. History Snapshot 正确（含 Cash/Equity/PnL）",
      len(hist) >= 1 and all(k in hist[0] for k in
      ("Date", "Cash", "Stock_Value", "Total_Equity", "Realized_PnL", "Unrealized_PnL",
       "Total_PnL", "Return_Pct")), f"{len(hist)} 行")

n1 = len(read_csv(d4, "portfolio_50000_history.csv"))
run_pf(d4, prices={"AMD": Decimal("700.00"), "META": Decimal("700.00")})
n2 = len(read_csv(d4, "portfolio_50000_history.csv"))
check("19. 重复运行不产生重复 snapshot", n1 == n2, f"{n1} -> {n2}")

t1 = len(read_csv(d4, "portfolio_50000_transactions.csv"))
run_pf(d4, prices={"AMD": Decimal("700.00"), "META": Decimal("700.00")})
t2 = len(read_csv(d4, "portfolio_50000_transactions.csv"))
check("18. 重复运行不产生重复 transaction", t1 == t2, f"{t1} -> {t2}")

for _ in range(5):
    run_pf(d4, prices={"AMD": Decimal("700.00"), "META": Decimal("700.00")})
m_final = json.loads((d4 / "portfolio_50000_meta.json").read_text(encoding="utf-8"))
check("20. 多次运行后 Initial Capital 恒为 50000（不重置）",
      Decimal(m_final["initial_capital"]) == Decimal("50000.00"), m_final["initial_capital"])

# ---------------------------------------------------------------- 21 Stop Loss 同步
print("\n--- Stop Loss 与 Review 联动 ---")
d5 = mk_fixture([core("AMD", TODAY, "630.48")])
run_pf(d5, prices={"AMD": Decimal("630.48")})
rows = list(csv.DictReader(open(d5 / "trade_history.csv", encoding="utf-8")))
for row in rows:
    if row["Ticker"] == "AMD":
        row["Status"] = "Period_Matured"
        row["Exit_Date"] = TODAY
        row["Exit_Price"] = "680.00"
with open(d5 / "trade_history.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=TH_COLS); w.writeheader()
    for row in rows: w.writerow(row)
r5 = run_pf(d5, prices={})
check("21. Review 终态（Period_Matured）正确同步 SELL",
      r5["realized_pnl"] == (Decimal("15") * Decimal("49.52")).quantize(Decimal("0.01")),
      str(r5["realized_pnl"]))

# ---------------------------------------------------------------- 24-25 空仓 / 全卖
print("\n--- 空 Portfolio / 全部卖出 ---")
d6 = mk_fixture([])
r6 = run_pf(d6, prices={})
check("24. 空 Portfolio 正确处理", r6["total_equity"] == Decimal("50000.00")
      and r6["stock_value"] == Decimal("0.00") and r6["cash"] == Decimal("50000.00"),
      str(r6["total_equity"]))

r7 = run_pf(d5, prices={})   # d5 已全部卖出
check("25. 全部卖出后 Cash/Equity 正确",
      r7["stock_value"] == Decimal("0.00") and r7["total_equity"] == r7["cash"]
      and r7["cash"] == (Decimal("50000.00") - Decimal("9457.20") + Decimal("15") * Decimal("680.00")).quantize(Decimal("0.01")),
      f"cash={r7['cash']} equity={r7['total_equity']}")

# ---------------------------------------------------------------- 26 金额精度
print("\n--- 金额精度 ---")
all_txn = read_csv(d5, "portfolio_50000_transactions.csv")
ok_prec = True
for t in all_txn:
    for f in ("Price", "Amount", "Realized_PnL", "Cash_After"):
        v = (t.get(f) or "").strip()
        if v and len(v.split(".")[-1]) > 2:
            ok_prec = False
check("26. 金额一律 2 位小数，无浮点毛刺", ok_prec, f"{len(all_txn)} 条交易")

# ---------------------------------------------------------------- 27-29 闸门
print("\n--- 历史闸门 / Unit 上限 / 预算 ---")
old_date = "2020-01-01"
d8 = mk_fixture([core("OLD1", old_date, "100.00")])
run_pf(d8, prices={})
check("27. start_date 之前的历史推荐不建仓（不虚构历史）",
      len([p for p in read_csv(d8, "portfolio_50000_positions.csv") if p["Status"] == "OPEN"]) == 0)

d9 = mk_fixture([core("T1", TODAY, "100.00"), core("T2", TODAY, "100.00"),
                 core("T3", TODAY, "100.00"), core("T4", TODAY, "100.00"),
                 core("T5", TODAY, "100.00")])
run_pf(d9, prices={})
open_cnt = len([p for p in read_csv(d9, "portfolio_50000_positions.csv") if p["Status"] == "OPEN"])
check("28. 浮动只数（#4）：同时持仓在 3-5 只区间", 3 <= open_cnt <= 5, f"{open_cnt} 个")

d10 = mk_fixture([core("EXP", TODAY, "250.00")])
run_pf(d10, prices={})
pp = [p for p in read_csv(d10, "portfolio_50000_positions.csv") if p["Status"] == "OPEN"]
check("29. 实际投入不超过 Unit 预算 10000",
      len(pp) == 1 and Decimal(pp[0]["Cost_Basis"]) <= Decimal("10000.00")
      and int(pp[0]["Shares"]) == 40, pp[0]["Cost_Basis"] if pp else "-")

# ---------------------------------------------------------------- 22 Dashboard 导出
print("\n--- Dashboard 导出 ---")
de = _load("demod", REPO / "dashboard_export.py")
built = de.build_portfolio(d4)
check("22. build_portfolio 返回完整字段",
      built is not None and all(k in built for k in
      ("portfolio_id", "initial_capital", "cash", "stock_value", "total_equity",
       "realized_pnl", "unrealized_pnl", "total_pnl", "return_pct",
       "positions", "transactions", "equity_curve")),
      f"{len(built.get('positions', []))} 持仓 / {len(built.get('transactions', []))} 流水"
      if built else "None")
check("22b. Dashboard 金额 2 位小数",
      built is not None and all(
          v is None or round(v, 2) == v
          for v in (built["initial_capital"], built["cash"], built["stock_value"],
                    built["total_equity"], built["total_pnl"])),
      str(built["total_equity"]) if built else "-")
check("22c. Equity Curve 起点恒为 $50,000",
      built is not None and built["equity_curve"]
      and built["equity_curve"][0]["total_equity"] == 50000.0
      and built["equity_curve"][0]["date"] == built["start_date"],
      str(built["equity_curve"][0]) if built and built["equity_curve"] else "-")
check("22e. Equity Curve 单调按日期排列且终点等于当前权益",
      built is not None and len(built["equity_curve"]) >= 1
      and built["equity_curve"][-1]["total_equity"] == built["total_equity"],
      f"{built['equity_curve'][-1]['total_equity']} vs {built['total_equity']}" if built else "-")
no_pf = de.build_portfolio(Path(tempfile.mkdtemp(prefix="empty_")))
check("22d. 未初始化时返回 None（前端不报错）", no_pf is None)

# ---------------------------------------------------------------- #4 单元测试：动态 Unit + 百分比仓位
def _mk_pos_4(ticker, mv):
    return {"Ticker": ticker, "Status": "OPEN", "Market_Value": str(mv), "Unit_ID": "U001"}


def _mk_txn_4(ticker, action, amount):
    return {"Ticker": ticker, "Action": action, "Amount": str(amount), "Date": "2026-10-01"}


# unit_dollars_for：缺评分 → 退化为固定 1 Unit（向后兼容，§4.7）
check("4a. 缺 AI_Score → 1 Unit ($10,000)，equity=50k",
      pf.unit_dollars_for({}, Decimal("50000")) == Decimal("10000"))
# 缺评分 + equity 较小 → 受 25% 单只上限钳制
check("4b. 缺评分 equity=30k → 受 25% 钳制为 $7,500",
      pf.unit_dollars_for({}, Decimal("30000")) == Decimal("7500"))
# 评分 60 → factor 0.5 → $5,000
check("4c. AI_Score=60 → 0.5 Unit ($5,000)",
      pf.unit_dollars_for({"AI_Score": 60}, Decimal("50000")) == Decimal("5000"))
# 评分 75 → factor 1.0 → $10,000
check("4d. AI_Score=75 → 1.0 Unit ($10,000)",
      pf.unit_dollars_for({"AI_Score": 75}, Decimal("50000")) == Decimal("10000"))
# 评分 90 → factor 1.25（上钳）→ $12,500
check("4e. AI_Score=90 → 1.25 Unit 上限 ($12,500)",
      pf.unit_dollars_for({"AI_Score": 90}, Decimal("50000")) == Decimal("12500"))
# 评分 100 → 仍钳到 1.25 → $12,500
check("4f. AI_Score=100 → 仍钳到 1.25 Unit ($12,500)",
      pf.unit_dollars_for({"AI_Score": 100}, Decimal("50000")) == Decimal("12500"))
# 评分非法（非数字）→ 视为缺失 → 1 Unit
check("4g. AI_Score 非法(非数字) → 退化为 1 Unit",
      pf.unit_dollars_for({"AI_Score": "n/a"}, Decimal("50000")) == Decimal("10000"))

# _within_alloc：四维占比预审（单只≤25% / 总股票≤80%）
ok0, why0 = pf._within_alloc({}, [], [], Decimal("50000"))
check("4h. 空仓 equity=50k 通过占比预审", ok0 is True and why0 == "")
# 单只 25% 上限的真正保护在 unit_dollars_for 内（高评分也被钳到 equity*25%）
check("4i. AI_Score=90/equity30k → 仍受 25% 钳制为 $7,500（单只上限保护）",
      pf.unit_dollars_for({"AI_Score": 90}, Decimal("30000")) == Decimal("7500"))
# 因此 _within_alloc 对该场景放行（尺寸已 ≤25%）
ok1, why1 = pf._within_alloc({"AI_Score": 90}, [], [], Decimal("30000"))
check("4i'. 评分90/equity30k 尺寸已钳到 25% → 占比预审放行", ok1 is True and why1 == "")
pos_hi = [_mk_pos_4("X", 35000)]
txn_hi = [_mk_txn_4("X", "BUY", 35000)]   # cash=15k, stock=35k → 股票占比 70%
ok2, why2 = pf._within_alloc({}, pos_hi, txn_hi, Decimal("50000"))
check("4j. 已有 70% 股票再买 1 Unit → 总股票将超 80% 被拦截", ok2 is False and "80%" in why2)
# 边界：股票 75%（37.5k）+ 新 1 Unit(10k) → proj=47.5k > 40k → 仍拦截
pos_75 = [_mk_pos_4("Y", 37500)]
txn_75 = [_mk_txn_4("Y", "BUY", 37500)]   # cash=12.5k, stock=37.5k → 股票占比 75%
ok2b, why2b = pf._within_alloc({}, pos_75, txn_75, Decimal("50000"))
check("4k. 已有 75% 股票再买 1 Unit → 总股票将超 80% 被拦截", ok2b is False and "80%" in why2b)

# ---------------------------------------------------------------- 清理
for dd in (d, d2, d3, d4, d5, d6, d8, d9, d10):
    shutil.rmtree(dd, ignore_errors=True)

total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
print("\n" + "=" * 70)
for name, ok, detail in results:
    if not ok:
        print(f"  FAILED: {name} {detail}")
print(f"结果：通过 {passed} / {total}")
print("=" * 70)
sys.exit(0 if passed == total else 1)
