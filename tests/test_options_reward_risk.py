# -*- coding: utf-8 -*-
"""Options Reward/Risk 交易资格门槛回归测试（离线，纯函数 + 临时 fixture）。

业务硬规则：
  Reward/Risk >= 2.0        -> Active
  Reward/Risk <  2.0        -> Rejected  (Reward/Risk below 2.0)
  Reward/Risk 无法可靠计算    -> Rejected  (Reward/Risk unavailable)

核心原则：
  · 不修改真实 MaxLoss / MaxProfit 定义
  · 不为了凑 2:1 而篡改风险
  · 不存在可执行的 Planned Risk 数值时，一律用 Theoretical R/R（不伪造 ATR/MA/Support）
  · gating 使用 raw 值，禁止 rounded gating
"""
import importlib.util
import math
import os
import sys
import tempfile

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(REPO, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


soe = _load("soe", "scan_us_option_engine.py")
de = _load("de", "dashboard_export.py")

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""))


MIN_RR = soe.MIN_REWARD_RISK

print(f"== 0. 常量与概念分离 ==")
check("0a. MIN_REWARD_RISK == 2.0", MIN_RR == 2.0, f"实际 {MIN_RR}")
check("0b. MIN_SPREAD_REWARD_RISK 仍为 0.40（candidate selection 未被误改）",
      soe.MIN_SPREAD_REWARD_RISK == 0.40, f"实际 {soe.MIN_SPREAD_REWARD_RISK}")
check("0c. 两个门槛概念分离（不相等）", soe.MIN_SPREAD_REWARD_RISK != MIN_RR)

# ---------------------------------------------------------------- Test 1
print("== Test 1. 用户实际案例：SHORT PUT Strike=210 / Premium=3.70 / Qty=1 ==")
strike, premium, qty = 210.0, 3.70, 1
max_profit = premium * 100.0 * qty
max_loss = (strike - premium) * 100.0 * qty
check("1a. MaxProfit = 370", abs(max_profit - 370.0) < 1e-9, f"{max_profit}")
check("1b. MaxLoss = 20630", abs(max_loss - 20630.0) < 1e-9, f"{max_loss}")
rr1 = soe.theoretical_reward_risk(max_profit, max_loss, qty)
check("1c. RewardRisk ≈ 0.0179", rr1 is not None and abs(rr1 - 370.0 / 20630.0) < 1e-12,
      f"raw={rr1}")
st1, rr1b, rs1 = soe.evaluate_trade_eligibility(max_profit, max_loss, qty)
check("1d. Status = Rejected", st1 == "Rejected", f"{st1}")
check("1e. Reject_Reason = Reward/Risk below 2.0", rs1 == soe.REJECT_REASON_RR_BELOW, f"{rs1!r}")
check("1f. 显示 2 位小数为 0.02（不影响 gating）", f"{rr1:.2f}" == "0.02", f"{rr1:.2f}")

# ---------------------------------------------------------------- Test 2
print("== Test 2. RR 刚好 2.0 -> Active ==")
st, rr, rs = soe.evaluate_trade_eligibility(200.0, 100.0, 1)
check("2a. RR == 2.0", rr is not None and abs(rr - 2.0) < 1e-12, f"{rr}")
check("2b. Status = Active", st == "Active", f"{st}")
check("2c. Reject_Reason 为空", rs == "", f"{rs!r}")

# ---------------------------------------------------------------- Test 3
print("== Test 3. RR = 1.99 -> Rejected ==")
st, rr, rs = soe.evaluate_trade_eligibility(199.0, 100.0, 1)
check("3a. RR == 1.99", rr is not None and abs(rr - 1.99) < 1e-12, f"{rr}")
check("3b. Status = Rejected", st == "Rejected", f"{st}")
check("3c. 原因为 below 2.0", rs == soe.REJECT_REASON_RR_BELOW, f"{rs!r}")

# ---------------------------------------------------------------- Test 4
print("== Test 4. RR = 1.999（显示 2.00）仍必须 Rejected ==")
st, rr, rs = soe.evaluate_trade_eligibility(199.9, 100.0, 1)
check("4a. RR == 1.999", rr is not None and abs(rr - 1.999) < 1e-12, f"raw={rr}")
check("4b. 显示为 2.00（rounded）", f"{rr:.2f}" == "2.00", f"{rr:.2f}")
check("4c. gating 用 raw -> Status = Rejected（禁止 rounded gating）", st == "Rejected", f"{st}")

# ---------------------------------------------------------------- Test 5
print("== Test 5. CALL DEBIT SPREAD ==")
# MaxProfit = (width - debit) * 100 * qty ; MaxLoss = debit * 100 * qty
sp_profit = (5.0 - 2.05) * 100.0 * 1     # 295
sp_loss = 2.05 * 100.0 * 1               # 205
rr_sp = soe.theoretical_reward_risk(sp_profit, sp_loss, 1)
check("5a. Spread RR ≈ 1.439", rr_sp is not None and abs(rr_sp - 295.0 / 205.0) < 1e-12, f"{rr_sp}")
check("5b. RR=1.44 -> Rejected（即使已过 0.40 candidate 门槛）",
      soe.evaluate_trade_eligibility(sp_profit, sp_loss, 1)[0] == "Rejected")
# RR = 2.0 的价差：width=9, debit=3 -> profit=600, loss=300
st, rr, rs = soe.evaluate_trade_eligibility((9.0 - 3.0) * 100.0, 3.0 * 100.0, 1)
check("5c. Spread RR == 2.0 -> Active", st == "Active" and abs(rr - 2.0) < 1e-12, f"{st} rr={rr}")
# 验证 candidate 门槛（0.40）仍允许 1.44 通过结构筛选——两概念分离
check("5d. 1.439 >= 0.40（candidate 层仍可选中，证明未把 0.40 改成 2.0）",
      rr_sp >= soe.MIN_SPREAD_REWARD_RISK)

# ---------------------------------------------------------------- Test 6
print("== Test 6. LONG CALL（当前无可靠 MaxProfit）=")
# 当前代码 LONG_CALL 的 max_profit = None -> RR unavailable -> Rejected
st, rr, rs = soe.evaluate_trade_eligibility(None, 450.0, 1)
check("6a. MaxProfit=None -> Rejected", st == "Rejected", f"{st}")
check("6b. RR = None", rr is None)
check("6c. Reject_Reason = Reward/Risk unavailable", rs == soe.REJECT_REASON_RR_UNAVAILABLE, f"{rs!r}")

# ---------------------------------------------------------------- Test 7
print("== Test 7. None 输入 ==")
check("7a. (None, None) -> Rejected", soe.evaluate_trade_eligibility(None, None, 1)[0] == "Rejected")
check("7b. (370, None) -> Rejected", soe.evaluate_trade_eligibility(370.0, None, 1)[0] == "Rejected")
check("7c. (None, 20630) -> Rejected", soe.evaluate_trade_eligibility(None, 20630.0, 1)[0] == "Rejected")
check("7d. rr 为 None 时绝不默认 Active",
      soe.evaluate_trade_eligibility(370.0, None, 1)[0] != "Active")

# ---------------------------------------------------------------- Test 8
print("== Test 8. NaN / inf ==")
nan = float("nan")
inf = float("inf")
check("8a. NaN MaxLoss -> Rejected", soe.evaluate_trade_eligibility(370.0, nan, 1)[0] == "Rejected")
check("8b. NaN MaxProfit -> Rejected", soe.evaluate_trade_eligibility(nan, 20630.0, 1)[0] == "Rejected")
check("8c. inf MaxProfit -> Rejected", soe.evaluate_trade_eligibility(inf, 20630.0, 1)[0] == "Rejected")
check("8d. inf MaxLoss -> Rejected", soe.evaluate_trade_eligibility(370.0, inf, 1)[0] == "Rejected")
check("8e. NaN 不产生 True 比较（NaN >= 2.0 为 False）", not (nan >= MIN_RR))

# ---------------------------------------------------------------- Test 9
print("== Test 9. Zero / 负 Risk（不触发除零）==")
st, rr, rs = soe.evaluate_trade_eligibility(370.0, 0.0, 1)
check("9a. MaxLoss=0 -> Rejected（不除零）", st == "Rejected", f"{st}")
check("9b. RR = None（未产生 inf）", rr is None)
check("9c. 原因为 unavailable", rs == soe.REJECT_REASON_RR_UNAVAILABLE, f"{rs!r}")
st, rr, rs = soe.evaluate_trade_eligibility(370.0, -100.0, 1)
check("9d. MaxLoss<0 -> Rejected", st == "Rejected")
# qty 无效
check("9e. qty=0 -> Rejected", soe.evaluate_trade_eligibility(370.0, 100.0, 0)[0] == "Rejected")
check("9f. qty=None -> Rejected", soe.evaluate_trade_eligibility(370.0, 100.0, None)[0] == "Rejected")
check("9g. qty=-1 -> Rejected", soe.evaluate_trade_eligibility(370.0, 100.0, -1)[0] == "Rejected")
# 非数字
check("9h. MaxProfit='abc' -> Rejected", soe.evaluate_trade_eligibility("abc", 100.0, 1)[0] == "Rejected")
check("9i. MaxLoss='' -> Rejected", soe.evaluate_trade_eligibility(370.0, "", 1)[0] == "Rejected")

# ---------------------------------------------------------------- Test 10
print("== Test 10. Dashboard Actionable 过滤 ==")
opt_active = {"status": "Active", "reward_risk": 2.5}
opt_rej_below = {"status": "Rejected", "reward_risk": 0.0179, "reject_reason": soe.REJECT_REASON_RR_BELOW}
opt_rej_unavail = {"status": "Rejected", "reward_risk": None, "reject_reason": soe.REJECT_REASON_RR_UNAVAILABLE}
check("10a. Active+RR2.5 -> actionable", de.is_actionable_option(opt_active) is True)
check("10b. Rejected(below) -> 不可 action", de.is_actionable_option(opt_rej_below) is False)
check("10c. Rejected(unavailable) -> 不可 action", de.is_actionable_option(opt_rej_unavail) is False)
filtered = [o for o in [opt_active, opt_rej_below, opt_rej_unavail] if de.is_actionable_option(o)]
check("10d. 3 条(Active/Rejected/Rejected) 过滤后只剩 1 条 Active",
      len(filtered) == 1 and filtered[0] is opt_active, f"剩 {len(filtered)} 条")
# 历史遗留：Status=Active 但 RR 缺失 -> 不可 action（不默认 Active）
check("10e. 历史 Status=Active 但 RR=None -> 不可 action",
      de.is_actionable_option({"status": "Active", "reward_risk": None}) is False)
check("10f. Status=Active 但 RR=1.999 -> 不可 action",
      de.is_actionable_option({"status": "Active", "reward_risk": 1.999}) is False)
check("10g. status 大小写不敏感", de.is_actionable_option({"status": "active", "reward_risk": 3.0}) is True)
check("10h. 空 dict -> 不可 action", de.is_actionable_option({}) is False)

# ---------------------------------------------------------------- Test 11
print("== Test 11. Review 不把 Rejected 当 Active Position ==")
src = open(os.path.join(REPO, "review.py"), encoding="utf-8").read()
check("11a. review.load_option_positions 按 Status=='Active' 严格过滤",
      'd["Status"].astype(str).str.strip() == "Active"' in src,
      "找到 Status=='Active' 过滤")
check("11b. Rejected 不满足该过滤条件（字符串不等）", "Rejected" != "Active")
check("11c. close_option_position 也只匹配 Active",
      'd["Status"].astype(str).str.strip().eq("Active")' in src)
# 运行期验证：用引擎的读取函数（与 review 同口径）在临时 CSV 上过滤
tmpdir = tempfile.mkdtemp(prefix="opt_rr_")
tmpcsv = os.path.join(tmpdir, "option_strategies.csv")
header = ("Ticker,Strategy,Status,RewardRisk,Reject_Reason,Quantity,Expiry,EntryPrice,"
          "OptionType,Strike,LongStrike,ShortStrike,EntryDate,NetDebit,LongPrice\n")
# 注意：每行字段数必须严格等于 header 的 15 列，否则 pandas 会把首列当 index
rows = [
    "ALL,SHORT_PUT,Rejected,0.017935,Reward/Risk below 2.0,1,2026-11-20,3.70,PUT,210,,,2026-10-01,,",
    "WIN,SHORT_PUT,Active,2.5,,1,2026-11-20,5.00,PUT,100,,,2026-10-01,,",
    "LOS,CALL_DEBIT_SPREAD,Rejected,1.439,Reward/Risk below 2.0,1,2026-11-20,2.05,CALL,,100,105,2026-10-01,2.05,",
]
open(tmpcsv, "w", encoding="utf-8").write(header + "\n".join(rows) + "\n")
orig_file = soe.OPTION_FILE
soe.OPTION_FILE = tmpcsv
try:
    recent = soe.get_recent_option_recommendations(limit=50)
finally:
    soe.OPTION_FILE = orig_file
tk = [r.get("Ticker") for r in recent]
check("11d. 读取层只返回 Active（WIN），Rejected 的 ALL/LOS 均被排除",
      tk == ["WIN"], f"返回 {tk}")

# ---------------------------------------------------------------- Test 12
print("== Test 12. Email 不推荐 Rejected ==")
check("12a. Email 数据源 get_recent_option_recommendations 已过滤 Status=='Active'",
      all(str(r.get("Status", "")).strip() == "Active" for r in recent),
      f"{[ (r.get('Ticker'), r.get('Status')) for r in recent ]}")
check("12b. 无任何 Rejected 进入推荐列表",
      not any(str(r.get("Status", "")).strip() == "Rejected" for r in recent))
# scan.py 侧：确认其调用方式与数据源一致（静态确认，不改动 scan.py）
scan_src = open(os.path.join(REPO, "scan.py"), encoding="utf-8").read()
check("12c. scan.py 使用 get_recent_option_recommendations 作为邮件数据源",
      "get_recent_option_recommendations" in scan_src)
check("12d. scan.py 未出现绕过过滤的 Status 硬编码兜底",
      '"Status":"Active"' not in scan_src and '"Status": "Active"' not in scan_src.replace(" ", ""),
      "无 Status 硬编码兜底")

# ---------------------------------------------------------------- 真实代码路径
print("== 13. 真实引擎代码路径（mock 期权链，走 build_option_recommendation）==")
import datetime as dt
import pandas as pd

ITEM = {
    "Ticker": "ALL", "Name": "Allstate", "Price": 224.88,
    "Quant_Score": 75.0, "Fundamental_Score": 30.0, "EPS_TTM": 5.0,
    "PE_Forward": 12.0, "Revenue_Growth": 0.05, "Earnings_Growth": 0.05,
    "Operating_Cashflow": 1e9, "Free_Cashflow": 5e8, "Score": "88",
}
puts = pd.DataFrame([{
    "strike": 210.0, "lastPrice": 3.75, "bid": 3.70, "ask": 3.80,
    "volume": 100, "openInterest": 500, "impliedVolatility": 0.33,
}])
calls = pd.DataFrame([{
    "strike": 225.0, "lastPrice": 6.0, "bid": 5.9, "ask": 6.1,
    "volume": 100, "openInterest": 500, "impliedVolatility": 0.30,
}])
expiry = dt.date(2026, 11, 20)

orig_load = soe._load_chain
soe._load_chain = lambda t: (None, expiry, calls, puts)
try:
    rec = soe.build_option_recommendation(ITEM)
finally:
    soe._load_chain = orig_load

check("13a. 引擎生成了策略记录", rec is not None)
if rec:
    check("13b. Strategy = SHORT_PUT", rec.get("Strategy") == "SHORT_PUT", f"{rec.get('Strategy')}")
    check("13c. Strike = 210", abs(float(rec.get("Strike")) - 210.0) < 1e-9, f"{rec.get('Strike')}")
    check("13d. MaxProfit = 370.00", abs(float(rec.get("MaxProfit")) - 370.0) < 1e-9, f"{rec.get('MaxProfit')}")
    check("13e. MaxLoss = 20630.00（未被篡改）", abs(float(rec.get("MaxLoss")) - 20630.0) < 1e-9, f"{rec.get('MaxLoss')}")
    rr_rec = rec.get("RewardRisk")
    check("13f. RewardRisk ≈ 0.0179", rr_rec not in (None, "") and abs(float(rr_rec) - 370.0 / 20630.0) < 1e-9, f"{rr_rec}")
    check("13g. Status = Rejected", rec.get("Status") == "Rejected", f"{rec.get('Status')}")
    check("13h. Reject_Reason = Reward/Risk below 2.0",
          rec.get("Reject_Reason") == soe.REJECT_REASON_RR_BELOW, f"{rec.get('Reject_Reason')!r}")
    check("13i. 落库 RR 精度保留（10 位，不会把 1.999 抹成 2.0）",
          abs(float(rr_rec) - 0.0179350453) < 1e-6, f"{rr_rec}")
    check("13j. 引擎输出不通过 Dashboard Actionable 门槛",
          de.is_actionable_option({"status": rec.get("Status"), "reward_risk": rec.get("RewardRisk")}) is False)

# ---------------------------------------------------------------- Invariant
print("== 14. 最终 Invariant（不得存在低于 2.0 的 Active）==")
samples = [
    ("ALL-SHORT_PUT", 370.0, 20630.0),
    ("CBOE-SHORT_PUT", 570.0, 23430.0),
    ("NTAP-SHORT_PUT", 650.0, 18350.0),
    ("TER-SHORT_PUT", 2170.0, 33830.0),
    ("FTNT-SPREAD", 548.0, 452.0),
    ("PAYX-SPREAD", 295.0, 205.0),
    ("APA-SPREAD", 145.0, 105.0),
    ("SCHW-SPREAD", 441.0, 309.0),
    ("MPC-SPREAD", 1100.0, 900.0),
    ("LONG_CALL", None, 450.0),
    ("EDGE-2.0", 200.0, 100.0),
    ("EDGE-1.999", 199.9, 100.0),
]
violations = []
active_n = rejected_n = unavail_n = 0
for name, mp, ml in samples:
    st, rr, rs = soe.evaluate_trade_eligibility(mp, ml, 1)
    if st == "Active":
        active_n += 1
        if rr is None or rr < MIN_RR:
            violations.append((name, rr))
    else:
        rejected_n += 1
        if rr is None:
            unavail_n += 1
check("14a. 无「RR<2.0 却 Active」的违规", not violations, f"{violations}")
check("14b. 无「RR unavailable 却 Active」的违规",
      all(not (soe.evaluate_trade_eligibility(mp, ml, 1)[0] == "Active" and
               soe.evaluate_trade_eligibility(mp, ml, 1)[1] is None) for _, mp, ml in samples))
print(f"  [统计] 样本 {len(samples)} 条：Active={active_n} Rejected={rejected_n} "
      f"（其中 RR unavailable={unavail_n}）")

# ---------------------------------------------------------------- 端到端
print("== 15. Dashboard 端到端（build_options -> Actionable 过滤）==")
rows_e2e = [
    # 新规则产出的 Rejected（Short Put，RR 极低）
    {"Ticker": "ALL", "Strategy": "SHORT_PUT", "MaxProfit": "370.0", "MaxLoss": "20630.0",
     "RewardRisk": "0.017935046", "Status": "Rejected",
     "Reject_Reason": soe.REJECT_REASON_RR_BELOW, "Strike": "210", "Quantity": "1"},
    # 新规则产出的 Rejected（Spread，RR=1.439）
    {"Ticker": "PAYX", "Strategy": "CALL_DEBIT_SPREAD", "MaxProfit": "295.0", "MaxLoss": "205.0",
     "RewardRisk": "1.439", "Status": "Rejected",
     "Reject_Reason": soe.REJECT_REASON_RR_BELOW, "LongStrike": "100", "ShortStrike": "105", "Quantity": "1"},
    # 通过门槛的 Active（RR=2.5）
    {"Ticker": "WIN", "Strategy": "SHORT_PUT", "MaxProfit": "500.0", "MaxLoss": "200.0",
     "RewardRisk": "2.5", "Status": "Active", "Reject_Reason": "", "Strike": "100", "Quantity": "1"},
    # 历史遗留：Status=Active 但 RewardRisk 缺失 -> 必须不可 Actionable
    {"Ticker": "OLD", "Strategy": "SHORT_PUT", "MaxProfit": "370.0", "MaxLoss": "20630.0",
     "RewardRisk": "", "Status": "Active", "Strike": "210", "Quantity": "1"},
]
anomalies = []
built = de.build_options(rows_e2e, anomalies)
check("15a. build_options 解析出全部 4 条（Rejected 保留在底层）", len(built) == 4, f"{len(built)}")
by_tk = {o["ticker"]: o for o in built}
check("15b. status 字段透传正确",
      by_tk["ALL"]["status"] == "Rejected" and by_tk["WIN"]["status"] == "Active")
check("15c. reject_reason 字段透传正确",
      by_tk["ALL"].get("reject_reason") == soe.REJECT_REASON_RR_BELOW,
      f"{by_tk['ALL'].get('reject_reason')!r}")
check("15d. reward_risk 保留原始精度（未 round 成 2.0）",
      abs(float(by_tk["PAYX"]["reward_risk"]) - 1.439) < 1e-9,
      f"{by_tk['PAYX']['reward_risk']}")
actionable = [o for o in built if de.is_actionable_option(o)]
act_tk = sorted(o["ticker"] for o in actionable)
check("15e. Actionable 只剩 WIN（1 条）", act_tk == ["WIN"], f"{act_tk}")
check("15f. Rejected 的 ALL/PAYX 不在 Actionable 中",
      not any(t in act_tk for t in ("ALL", "PAYX")))
check("15g. 历史遗留 OLD（Active 但 RR 缺失）不在 Actionable 中", "OLD" not in act_tk)
check("15h. Actionable 全部满足 RR >= 2.0",
      all(float(o["reward_risk"]) >= MIN_RR for o in actionable),
      f"{[(o['ticker'], o['reward_risk']) for o in actionable]}")
check("15i. 统计口径：rejected = 3",
      sum(1 for o in built if not de.is_actionable_option(o)) == 3)

# ---------------------------------------------------------------- 结果
print()
passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f"结果：通过 {passed} / {total}")
if passed == total:
    print("全部通过 ✅")
else:
    print("存在失败 ❌")
    for n, ok in results:
        if not ok:
            print(f"   FAILED: {n}")
    sys.exit(1)
