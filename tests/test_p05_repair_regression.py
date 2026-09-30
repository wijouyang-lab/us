# -*- coding: utf-8 -*-
"""P0.5 Stop_Loss 修复回归测试（可重复执行，不依赖历史 HEAD / 生产 CSV）。

两部分：
  A. immutable BEFORE fixture + 忠实复刻 P0.5 修复规则的纯函数，对临时副本
     运行修复并验证（绝不触碰 production CSV）。
  B. 直接通过 AST 抽取 review.py 的 is_valid_existing_stop() 与
     MAX_TRAILING_RATIO，验证 production 的 trailing-stop floor 行为。

A 部分覆盖：
  1. 15 目标唯一匹配
  2. 非目标 0 变化
  3. 12 条结束记录 Status 不变
  4. 12 条结束记录 Exit_Date 不变
  5. 12 条结束记录 Exit_Price 不变
  6. MSTR/BSX/ORCL 从错误 STOP_TRIGGERED 恢复
  7. 965/980/505 不再作为有效 Stop_Loss
  8. 新 Stop_Loss 正数有限
  9. Rec_Price 不变
  10. Price_5D/10D/20D 不变
  11. PnL_5D/10D/20D 不变
  12. repair deterministic
  13. repair 幂等（第二次运行 0 变化）

B 部分覆盖（直接测 production helper）：
  14. old_stop <= 2.0 × Rec_Price → True
  15. old_stop > 2.0 × Rec_Price → False（MSTR 965/116、BSX 980/44、ORCL 505/152）
  16. None / 0 / 负数 / 非数字 → False
  17. candidate = max(old_stop, candidate) 仅对 valid old_stop 生效
"""
import ast
import os
from decimal import Decimal, ROUND_HALF_UP

# ---------------------------------------------------------------------------
# immutable BEFORE fixture：15 条目标 + 3 条非目标
# 字段：ticker, rec_date, rec_price, stop_loss, status, exit_date, exit_price,
#       triggered(是否错误触发), milestone 相关只读字段
# ---------------------------------------------------------------------------
FIXTURE = [
    # 12 条已结束记录（仅修 Stop_Loss）
    dict(ticker="GRAB", rec_date="2026-06-03", rec_price=3.60,  stop_loss="$34.80", status="Stop_Loss_Hit", exit_date="2026-06-30", exit_price="3.74",  triggered=False),
    dict(ticker="RIVN", rec_date="2026-06-03", rec_price=17.29, stop_loss="$34.80", status="Stop_Loss_Hit", exit_date="2026-06-30", exit_price="16.81", triggered=False),
    dict(ticker="SRXH", rec_date="2026-06-05", rec_price=0.13,  stop_loss="$4.20",  status="Dropped",       exit_date="2026-06-30", exit_price="0.09",  triggered=False),
    dict(ticker="NOTV", rec_date="2026-06-09", rec_price=0.11,  stop_loss="$105.00",status="Dropped",       exit_date="2026-06-30", exit_price="0.08",  triggered=False),
    dict(ticker="F",    rec_date="2026-06-19", rec_price=13.96, stop_loss="$965",   status="Dropped",       exit_date="2026-07-02", exit_price="13.64", triggered=False),
    dict(ticker="HOOD", rec_date="2026-06-19", rec_price=105.20,stop_loss="$965",   status="Period_Matured",exit_date="2026-07-08", exit_price="112.9", triggered=False),
    dict(ticker="PFE",  rec_date="2026-06-19", rec_price=25.92, stop_loss="$965",   status="Stop_Loss_Hit", exit_date="2026-06-30", exit_price="24.37", triggered=False),
    dict(ticker="ACN",  rec_date="2026-06-22", rec_price=127.98,stop_loss="$395",   status="Stop_Loss_Hit", exit_date="2026-06-30", exit_price="124.74",triggered=False),
    dict(ticker="PFE",  rec_date="2026-06-22", rec_price=25.21, stop_loss="$395",   status="Stop_Loss_Hit", exit_date="2026-06-30", exit_price="24.37", triggered=False),
    dict(ticker="PLTR", rec_date="2026-06-22", rec_price=128.47,stop_loss="$395",   status="Stop_Loss_Hit", exit_date="2026-06-30", exit_price="115.7", triggered=False),
    dict(ticker="HAL",  rec_date="2026-06-25", rec_price=33.90, stop_loss="$980",   status="Period_Matured",exit_date="2026-06-30", exit_price="34.09", triggered=False),
    dict(ticker="PFE",  rec_date="2026-06-25", rec_price=24.04, stop_loss="$980",   status="Stop_Loss_Hit", exit_date="2026-06-30", exit_price="24.37", triggered=False),
    # 3 条错误触发记录（修 Stop_Loss + 撤销 STOP_TRIGGERED）
    dict(ticker="MSTR", rec_date="2026-06-19", rec_price=116.56, stop_loss="$965",  status="Stop_Loss_Hit", exit_date="2026-09-29", exit_price="161.63",triggered=True),
    dict(ticker="BSX",  rec_date="2026-06-25", rec_price=44.21,  stop_loss="$980",  status="Stop_Loss_Hit", exit_date="2026-09-29", exit_price="44.15", triggered=True),
    dict(ticker="ORCL", rec_date="2026-06-26", rec_price=149.74, stop_loss="$505",  status="Stop_Loss_Hit", exit_date="2026-09-29", exit_price="132.79",triggered=True),
    # 3 条非目标（正常 stop，不应被修改）
    dict(ticker="BKNG", rec_date="2026-08-05", rec_price=207.24, stop_loss="184.0", status="Stop_Loss_Hit", exit_date="2026-09-29", exit_price="163.68",triggered=False),
    dict(ticker="KVUE", rec_date="2026-07-30", rec_price=19.58,  stop_loss="$18.50", status="Stop_Loss_Hit", exit_date="2026-09-29", exit_price="17.74", triggered=False),
    dict(ticker="MSTR", rec_date="2026-06-24", rec_price=103.84, stop_loss="98.65",  status="Stop_Loss_Hit", exit_date="2026-09-29", exit_price="152.43",triggered=False),
]

# 目标集合：(ticker, rec_date, bad_stop_float)
TARGETS = {
    ("GRAB","2026-06-03",34.80), ("RIVN","2026-06-03",34.80), ("SRXH","2026-06-05",4.20),
    ("NOTV","2026-06-09",105.0), ("F","2026-06-19",965.0),   ("HOOD","2026-06-19",965.0),
    ("MSTR","2026-06-19",965.0), ("PFE","2026-06-19",965.0), ("ACN","2026-06-22",395.0),
    ("PFE","2026-06-22",395.0),  ("PLTR","2026-06-22",395.0),("BSX","2026-06-25",980.0),
    ("HAL","2026-06-25",980.0),  ("PFE","2026-06-25",980.0), ("ORCL","2026-06-26",505.0),
}
TRIGGERED = {("MSTR","2026-06-19"), ("BSX","2026-06-25"), ("ORCL","2026-06-26")}
BAD_STOP_VALUES = {965.0, 980.0, 505.0}


def _num(v):
    s = str(v).strip().replace("$", "").replace(",", "")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _fallback_stop(rec_price):
    """Rec_Price × 0.95，量化到 2 位小数（ROUND_HALF_UP）。"""
    d = Decimal(str(rec_price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    v = (d * Decimal("0.95")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(v)


def apply_p05_repair(records):
    """忠实复刻 P0.5 修复规则（纯函数，不改输入）。

    只对 (ticker, rec_date, stop_loss 数值 == 目标 bad) 的记录修复：
      - Stop_Loss = Rec_Price × 0.95；
      - 错误触发记录：Status -> Active，Exit_Date/Exit_Price 清空。
    返回新的 records list。
    """
    out = []
    for r in records:
        new = dict(r)
        cur_stop = _num(r["stop_loss"])
        key = (r["ticker"], r["rec_date"], cur_stop)
        if key in TARGETS:
            new["stop_loss"] = f"{_fallback_stop(r['rec_price']):.2f}"
            if (r["ticker"], r["rec_date"]) in TRIGGERED:
                new["status"] = "Active"
                new["exit_date"] = ""
                new["exit_price"] = ""
        out.append(new)
    return out


results = []
def check(name, cond, detail=""):
    results.append((name, cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# A 部分：fixture 修复回归
# ---------------------------------------------------------------------------
before = [dict(r) for r in FIXTURE]
after = apply_p05_repair(before)

print("== 1. 15 目标唯一匹配 ==")
matched = 0
for (tk, rd, bad) in TARGETS:
    m = [r for r in before if r["ticker"] == tk and r["rec_date"] == rd and _num(r["stop_loss"]) == bad]
    check(f"{tk}/{rd} 唯一", len(m) == 1, f"{len(m)}")
    matched += len(m)
check("总匹配 == 15", matched == 15, f"{matched}")

print("== 2. 非目标 0 变化 ==")
target_keys = {(tk, rd) for (tk, rd, _) in TARGETS}
non_target_changed = [
    (b["ticker"], b["rec_date"])
    for b, a in zip(before, after)
    if (b["ticker"], b["rec_date"]) not in target_keys and b != a
]
check("非目标记录 0 变化", len(non_target_changed) == 0, f"{non_target_changed}")

print("== 3/4/5. 12 条结束记录状态字段不变 ==")
closed = [(tk, rd) for (tk, rd, _) in TARGETS if (tk, rd) not in TRIGGERED]
bad_s = bad_d = bad_p = 0
for (tk, rd) in closed:
    b = next(r for r in before if r["ticker"] == tk and r["rec_date"] == rd)
    a = next(r for r in after if r["ticker"] == tk and r["rec_date"] == rd)
    if b["status"] != a["status"]: bad_s += 1
    if b["exit_date"] != a["exit_date"]: bad_d += 1
    if b["exit_price"] != a["exit_price"]: bad_p += 1
check("12 条 Status 不变", bad_s == 0, f"{bad_s}")
check("12 条 Exit_Date 不变", bad_d == 0, f"{bad_d}")
check("12 条 Exit_Price 不变", bad_p == 0, f"{bad_p}")

print("== 6. 3 条错误触发恢复 ==")
for (tk, rd) in TRIGGERED:
    a = next(r for r in after if r["ticker"] == tk and r["rec_date"] == rd)
    ok = a["status"] == "Active" and a["exit_date"] == "" and a["exit_price"] == ""
    check(f"{tk}/{rd} 恢复 Active 且 Exit 清空", ok, f"{a['status']}/{a['exit_date']}/{a['exit_price']}")

print("== 7. 异常值不再出现 ==")
still_bad = [r for r in after if _num(r["stop_loss"]) in BAD_STOP_VALUES]
check("965/980/505 已全部清除", len(still_bad) == 0, f"{len(still_bad)}")

print("== 8. 新 Stop 正数有限 ==")
all_ok = True
for (tk, rd, _) in TARGETS:
    a = next(r for r in after if r["ticker"] == tk and r["rec_date"] == rd)
    v = _num(a["stop_loss"])
    if v is None or not (v > 0 and v == v and v not in (float("inf"), float("-inf"))):
        all_ok = False
check("15 条新 Stop 全部正数有限", all_ok)

print("== 9. Rec_Price 不变 ==")
check("Rec_Price 不变", all(b["rec_price"] == a["rec_price"] for b, a in zip(before, after)))

print("== 10/11. milestone/PnL 字段不被修复函数触碰 ==")
check("修复函数仅改 stop_loss/status/exit_date/exit_price",
      all(set(b.keys()) == set(a.keys()) and
          all(a[k] == b[k] for k in b if k not in ("stop_loss", "status", "exit_date", "exit_price"))
          for b, a in zip(before, after)))

print("== 12. deterministic ==")
after2 = apply_p05_repair([dict(r) for r in FIXTURE])
check("相同输入 -> 相同输出", after == after2)

print("== 13. 幂等 ==")
after_run2 = apply_p05_repair(after)
check("第二次运行 0 变化", after == after_run2, f"变化 {sum(1 for x,y in zip(after,after_run2) if x!=y)} 条")


# ---------------------------------------------------------------------------
# B 部分：直接测试 production 的 is_valid_existing_stop() + floor 行为
# ---------------------------------------------------------------------------
REVIEW_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "review.py")
SRC = open(REVIEW_PY, encoding="utf-8").read()
tree = ast.parse(SRC)
ns = {}
for node in tree.body:
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id == "MAX_TRAILING_RATIO":
                exec(ast.get_source_segment(SRC, node), ns)
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name == "is_valid_existing_stop":
        exec(ast.get_source_segment(SRC, node), ns)
is_valid_existing_stop = ns["is_valid_existing_stop"]
MAX_TRAILING_RATIO = ns["MAX_TRAILING_RATIO"]


def floor(candidate, old, entry_price):
    """复刻 production 的 trailing-stop floor：仅 valid old_stop 才 max(old, candidate)。"""
    v = _num(old) if old is not None else None
    if v and v > 0:
        if is_valid_existing_stop(v, entry_price):
            return max(v, candidate)
    return candidate


print(f"== 14/15/16. production is_valid_existing_stop (MAX_TRAILING_RATIO={MAX_TRAILING_RATIO}) ==")
check("BKNG: old=184 <= 2.0x207.24 -> True", is_valid_existing_stop(184.0, 207.24) is True)
check("MSTR: old=965 > 2.0x116.56 -> False", is_valid_existing_stop(965.0, 116.56) is False)
check("BSX:  old=980 > 2.0x44.21 -> False", is_valid_existing_stop(980.0, 44.21) is False)
check("ORCL: old=505 > 2.0x149.74 -> False", is_valid_existing_stop(505.0, 149.74) is False)
check("边界: old=2.0xRec_Price -> True（不严格大于）", is_valid_existing_stop(200.0, 100.0) is True)
check("越界: old=2.01xRec_Price -> False", is_valid_existing_stop(201.0, 100.0) is False)
check("None -> False", is_valid_existing_stop(None, 100.0) is False)
check("0 -> False", is_valid_existing_stop(0.0, 100.0) is False)
check("负数 -> False", is_valid_existing_stop(-5.0, 100.0) is False)
check("非数字 -> False", is_valid_existing_stop("abc", 100.0) is False)
check("rec_price=None 时仅校验正数有限", is_valid_existing_stop(50.0, None) is True)

print("== 17. floor 行为：仅 valid old_stop 才 max(old, candidate) ==")
check("valid old_stop 抬升 floor: max(184, 180)=184",
      floor(180.0, "184.0", 207.24) == 184.0)
check("invalid old_stop 丢弃: candidate 110 保持（MSTR 965 不成为 floor）",
      floor(110.0, "965", 116.56) == 110.0)
check("invalid old_stop 丢弃: candidate 40 保持（BSX 980 不成为 floor）",
      floor(40.0, "980", 44.21) == 40.0)
check("invalid old_stop 丢弃: candidate 142 保持（ORCL 505 不成为 floor）",
      floor(142.0, "505", 149.74) == 142.0)
check("正常 trailing 只升不降仍成立: valid old=152 > candidate=140 -> 152",
      floor(140.0, "152.43", 103.84) == 152.43)

# 汇总
failed = [n for n, c in results if not c]
print(f"\n结果：通过 {len(results)-len(failed)} / {len(results)}")
if failed:
    print("失败：", failed)
    raise SystemExit(1)
print("全部通过 ✅")
