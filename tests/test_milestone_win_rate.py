# -*- coding: utf-8 -*-
"""P1 Milestone Win Rate 单元测试（离线，纯函数）。

通过 AST 抽取 review.py 的 compute_milestone_win_rate(events)。
events: list[dict]，每项含 pnl_5d/pnl_10d/pnl_20d（float 或 None）。

规则：Win = PnL > 0；Loss = PnL <= 0（含 0）；Eligible = Wins + Losses；
      缺失/未达标/Rec_Price 缺失/Price_N 缺失 → None，不进入分母。
"""
import ast
import os

REVIEW_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "review.py")
SRC = open(REVIEW_PY, encoding="utf-8").read()

def _extract():
    tree = ast.parse(SRC)
    ns = {}
    exec("import re, math, datetime, pandas as pd", ns)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            t = node.targets[0]
            if isinstance(t, ast.Name) and t.id == "INVALID_STRINGS":
                exec(ast.get_source_segment(SRC, node), ns)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "safe_float":
            exec(ast.get_source_segment(SRC, node), ns)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "compute_milestone_win_rate":
            exec(ast.get_source_segment(SRC, node), ns)
    return ns["compute_milestone_win_rate"]

compute_milestone_win_rate = _extract()

results = []
def check(name, cond, detail=""):
    results.append((name, cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""))

def ev(p5=None, p10=None, p20=None, **kw):
    d = {"pnl_5d": p5, "pnl_10d": p10, "pnl_20d": p20}
    d.update(kw)
    return d

# 1. PnL > 0 -> Win
r = compute_milestone_win_rate([ev(p5=5.0)])
check("1. PnL>0 -> Win (5D wins=1)", r["5D"]["wins"] == 1 and r["5D"]["losses"] == 0 and r["5D"]["eligible"] == 1)

# 2. PnL = 0 -> Loss
r = compute_milestone_win_rate([ev(p5=0.0)])
check("2. PnL=0 -> Loss", r["5D"]["losses"] == 1 and r["5D"]["wins"] == 0 and r["5D"]["eligible"] == 1)

# 3. PnL < 0 -> Loss
r = compute_milestone_win_rate([ev(p5=-3.0)])
check("3. PnL<0 -> Loss", r["5D"]["losses"] == 1 and r["5D"]["wins"] == 0)

# 4. 缺失 PnL -> 不进入分母
r = compute_milestone_win_rate([ev(p5=None)])
check("4. 缺失 PnL -> 不进入分母 (eligible=0)", r["5D"]["eligible"] == 0 and r["5D"]["win_rate"] is None)

# 5. 5D/10D/20D 独立统计
r = compute_milestone_win_rate([ev(p5=5.0, p10=-3.0, p20=2.0)])
check("5. 5D/10D/20D 独立", r["5D"]["wins"] == 1 and r["10D"]["losses"] == 1 and r["20D"]["wins"] == 1)

# 6. 未达到 milestone -> 不进入分母（=None，等同缺失）
r = compute_milestone_win_rate([ev(p10=None, p20=None)])
check("6. 未达标 -> 不进入分母", r["10D"]["eligible"] == 0 and r["20D"]["eligible"] == 0)

# 7. Rec_Price 缺失 -> PnL 缺失 -> 不进入分母（数据层 Rec_Price 缺失时 PnL 为空串）
r = compute_milestone_win_rate([ev(p5=None, p10=None, p20=None)])
check("7. Rec_Price 缺失 -> 不进入分母", r["5D"]["eligible"] == 0 and r["10D"]["eligible"] == 0 and r["20D"]["eligible"] == 0)

# 8. 正负混合样本
r = compute_milestone_win_rate([ev(p5=5), ev(p5=-3), ev(p5=2), ev(p5=-1)])
check("8. 正负混合: wins=2 losses=2", r["5D"]["wins"] == 2 and r["5D"]["losses"] == 2 and r["5D"]["eligible"] == 4)
check("   混合 win_rate = 50.0%", abs(r["5D"]["win_rate"] - 50.0) < 1e-9, f"{r['5D']['win_rate']}")

# 9. 全部 Win
r = compute_milestone_win_rate([ev(p5=1), ev(p5=2), ev(p5=3)])
check("9. 全部 Win -> win_rate 100%", r["5D"]["wins"] == 3 and abs(r["5D"]["win_rate"] - 100.0) < 1e-9)

# 10. 全部 Loss（含 0）
r = compute_milestone_win_rate([ev(p5=-1), ev(p5=-2), ev(p5=0)])
check("10. 全部 Loss -> win_rate 0%", r["5D"]["losses"] == 3 and r["5D"]["wins"] == 0 and abs(r["5D"]["win_rate"] - 0.0) < 1e-9)

# 11. 0 Eligible -> 不产生 ZeroDivisionError
r = compute_milestone_win_rate([])
check("11. 0 Eligible -> win_rate=None 无 ZeroDivisionError", r["5D"]["eligible"] == 0 and r["5D"]["win_rate"] is None)

# 12. 重复 ticker 不应被错误去重（两个相同 pnl 事件都计数）
r = compute_milestone_win_rate([ev(p5=5), ev(p5=5)])
check("12. 重复 ticker 不错误去重 (eligible=2)", r["5D"]["eligible"] == 2 and r["5D"]["wins"] == 2)

# 13. Status 不应改变统计结果
r_closed = compute_milestone_win_rate([ev(p5=5, status="CLOSED")])
r_active = compute_milestone_win_rate([ev(p5=5, status="Active")])
check("13. Status 不影响统计", r_closed["5D"] == r_active["5D"])

# 14. 已有 milestone 数据不得被修改（纯函数不 mutate 输入）
inp = [ev(p5=5), ev(p5=-3)]
before = [dict(x) for x in inp]
compute_milestone_win_rate(inp)
check("14. 输入 events 不被修改", inp == before)

# 15. 5D/10D/20D 各自 Eligible 独立（缺某一 milestone 只影响该档）
r = compute_milestone_win_rate([ev(p5=5, p10=None, p20=2)])
check("15. 缺失 10D 不影响 5D/20D", r["5D"]["eligible"] == 1 and r["10D"]["eligible"] == 0 and r["20D"]["eligible"] == 1)

# 汇总
failed = [n for n, c in results if not c]
print(f"\n结果：通过 {len(results)-len(failed)} / {len(results)}")
if failed:
    print("失败：", failed)
    raise SystemExit(1)
print("全部通过 ✅")
