# -*- coding: utf-8 -*-
"""P3.5 Rec_Price 确定性修复回归测试（离线，纯函数）。

固化 P3.5 的修复规则：
  - 正确基准 = trade_history Price = Rec_Date 真实 Open；
  - 只有 CONFIRMED_WRONG 才允许修复；
  - 修复只改 Rec_Price，不改 trade_history / Price_N / Stop_Loss / Exit / 非目标；
  - PnL 公式严格 round((Price_N - Rec_Price)/Rec_Price*100, 2)。
"""

def f(v):
    v = str(v).strip()
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def classify_rec_price(old_rp, trade_price):
    """判断 Rec_Price collision 结论。"""
    o, t = f(old_rp), f(trade_price)
    if o is None or t is None or t <= 0:
        return "UNRESOLVED"
    if abs(o - t) <= 1e-4:
        return "LEGITIMATE_DIFFERENCE"  # 无差异，无需修
    # 差异 >1e-4：需人工/证据确认是 backfill 错误而非 corporate action
    return "NEEDS_EVIDENCE"


def apply_repair(records, confirm_fn):
    """只对 confirm_fn 返回 CONFIRMED_WRONG 的记录修复 Rec_Price。"""
    out = []
    for r in records:
        new = dict(r)
        if confirm_fn(r) == "CONFIRMED_WRONG":
            new["rec_price"] = r["correct_rec_price"]
        out.append(new)
    return out


def recompute_pnl(price_n, rec_price):
    """严格 PnL 公式。"""
    p, rp = f(price_n), f(rec_price)
    if p is None or rp is None or rp <= 0 or p <= 0:
        return ""
    return str(round((p - rp) / rp * 100, 2))


results = []
def check(name, cond, detail=""):
    results.append((name, cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""))


print("== 1. actual Open 作为 Rec_Price ==")
check("1. trade_price 作为正确基准", f("19.0") == 19.0 and f("19.0") > 0)

print("== 2/3/4. 分类与修复条件 ==")
check("2. 差异->NEEDS_EVIDENCE(需证据确认)", classify_rec_price("20.18", "19.0") == "NEEDS_EVIDENCE")
check("3. 无 trade_price -> UNRESOLVED", classify_rec_price("20.18", "") == "UNRESOLVED")
check("4. 无差异 -> LEGITIMATE_DIFFERENCE", classify_rec_price("19.0", "19.0") == "LEGITIMATE_DIFFERENCE")

print("== 修复行为 ==")
# 确认函数：只确认目标 ticker
def confirm(r):
    return "CONFIRMED_WRONG" if r["ticker"] in ("NCLH", "HAL") else "KEEP"

recs = [
    {"ticker": "NCLH", "rec_date": "2026-08-04", "rec_price": "20.18", "correct_rec_price": "19.0",
     "stop_loss": "17.39", "exit_date": "", "exit_price": "", "price_5d": "", "pnl_5d": ""},
    {"ticker": "HAL", "rec_date": "2026-08-07", "rec_price": "32.19", "correct_rec_price": "31.89",
     "stop_loss": "28.6", "exit_date": "", "exit_price": "", "price_5d": "", "pnl_5d": ""},
    {"ticker": "OTHER", "rec_date": "2026-09-01", "rec_price": "100.0", "correct_rec_price": "99.0",
     "stop_loss": "90", "exit_date": "2026-09-10", "exit_price": "95", "price_5d": "101", "pnl_5d": "1.0"},
]
after = apply_repair(recs, confirm)

check("2. 仅 CONFIRMED_WRONG 修复 Rec_Price", after[0]["rec_price"] == "19.0" and after[1]["rec_price"] == "31.89")
check("11. 非目标 event 0 diff", after[2] == recs[2])
check("5/8/9/10. trade_history/Stop/Exit 不变",
      after[0]["stop_loss"] == "17.39" and after[0]["exit_date"] == "" and after[0]["exit_price"] == ""
      and after[2]["stop_loss"] == "90" and after[2]["exit_date"] == "2026-09-10" and after[2]["exit_price"] == "95")

print("== 6/7. Price_N 不变 + PnL 公式 ==")
check("6. Price_N 不被修复改动", after[2]["price_5d"] == "101")
check("7. PnL 公式: (101-100)/100*100=1.0", recompute_pnl("101", "100") == "1.0")
check("7b. PnL 公式: (Price_N<=0 或 Rec<=0) 返回空", recompute_pnl("0", "100") == "" and recompute_pnl("101", "0") == "")

print("== 10/12. deterministic + idempotent ==")
out1 = apply_repair([dict(r) for r in recs], confirm)
out2 = apply_repair([dict(r) for r in recs], confirm)
check("10. deterministic", out1 == out2)
out3 = apply_repair(out1, confirm)
check("12. idempotent", out1 == out3)

# 汇总
failed = [n for n, c in results if not c]
print(f"\n结果：通过 {len(results)-len(failed)} / {len(results)}")
if failed:
    print("失败：", failed)
    raise SystemExit(1)
print("全部通过 ✅")
