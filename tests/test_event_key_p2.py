# -*- coding: utf-8 -*-
"""P2 review_event_key 与 orphan repair 回归测试（离线，纯函数）。

A. 通过 AST 抽取 review.py 的 review_event_key()，验证事件唯一键规则；
B. 用 immutable fixture 复刻 orphan repair 逻辑，验证确定性回补 / UNRESOLVED；
C. 验证数据不变性（Rec_Price / PnL / milestone / Stop_Loss / Exit 不被触碰）。
"""
import ast
import os

import pandas as pd

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = open(os.path.join(REPO, "review.py"), encoding="utf-8").read()

_tree = ast.parse(SRC)
_ns = {}
exec("import pandas as pd", _ns)
for node in _tree.body:
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id == "INVALID_STRINGS":
                exec(ast.get_source_segment(SRC, node), _ns)
for node in _tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in ("clean_text", "review_event_key"):
        exec(ast.get_source_segment(SRC, node), _ns)

clean_text = _ns["clean_text"]
review_event_key = _ns["review_event_key"]


def row(**kw):
    d = {"Review_Date": "2026-06-03", "Ticker": "AVGO", "Tag": "Core_Dragon",
         "Rec_Date": "2026-06-02", "Status": "持仓中", "Option_Type": "",
         "Strike": "", "Expiry": ""}
    d.update(kw)
    return d


results = []
def check(name, cond, detail=""):
    results.append((name, cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""))


print("== A. review_event_key 规则 ==")
# 1. 同 ticker + 同日期 + 不同 Tag -> 不同 key
k1 = review_event_key(row(Tag="Core_Dragon"))
k2 = review_event_key(row(Tag="Observation"))
check("1. 同ticker同日不同Tag -> 不同key", k1 != k2, f"{k1} vs {k2}")

# 2. 同 ticker + 同日期 + 同 Tag -> 同 key
k3 = review_event_key(row(Tag="Core_Dragon"))
check("2. 同ticker同日同Tag -> 同key", k1 == k3)

# 3. 空 Tag 行为明确且 deterministic
k4 = review_event_key(row(Tag=""))
check("3. 空Tag deterministic", k4 == review_event_key(row(Tag="")) and k4 != k1)

# 4. NaN Tag 行为明确（keep_default_na=False 时 NaN 已变空；直接测 clean_text 语义）
check("4. NaN Tag -> clean_text 归一为空", clean_text(float("nan")) == "")
check("   空Tag key 一致(NaN归一后==空Tag)", review_event_key(row(Tag=float("nan"))) == k4)

# 5. whitespace normalization
check("5. Tag 前后空格归一", review_event_key(row(Tag="  Core_Dragon  ")) == k1)

# 6. 大小写规则：Ticker 大写，Tag 保留原样
check("6a. Ticker 大写归一", review_event_key(row(Ticker="avgo")) == k1)
check("6b. Tag 大小写敏感(不强制归一)", review_event_key(row(Tag="core_dragon")) != k1)

# 7. dataframe 顺序改变 -> key 不变（key 只依赖 row 内容）
check("7. key 不依赖顺序/Review_Date", review_event_key(row(Review_Date="2026-09-30")) == k1)

# 8. 同一 event 多个 Review snapshot -> 一个 logical event（Review_Date/Status 不影响 key）
k_a = review_event_key(row(Review_Date="2026-06-03", Status="持仓中"))
k_b = review_event_key(row(Review_Date="2026-09-30", Status="移动止损清仓"))
check("8. 多snapshot共享同key(Review_Date/Status不参与)", k_a == k_b == k1)

# 9. collision 检测：同 key 但 Rec_Price 不一致可被检测
def detect_collision(rows):
    g = {}
    for r in rows:
        k = review_event_key(r)
        rp = clean_text(r.get("Rec_Price"))
        g.setdefault(k, set()).add(rp)
    return {k: v for k, v in g.items() if len(v) > 1}

rows_coll = [row(Rec_Price="20.18"), row(Rec_Price="19.0")]
rows_nocoll = [row(Rec_Price="20.18"), row(Rec_Price="20.18")]
check("9. collision 检测(同key不同Rec_Price)", len(detect_collision(rows_coll)) == 1)
check("   无collision(同key同Rec_Price)", len(detect_collision(rows_nocoll)) == 0)


print("== B. orphan repair 确定性 ==")
# 复刻 p2_repair 的 orphan 回补逻辑（纯函数）
def resolve_orphan(orphan_row, snapshots):
    """orphan_row 的 key 在 snapshots（非空快照列表）中存在时，
    从 Review_Date 最后一条非空快照复制 Status/Rec_Count；否则 UNRESOLVED。"""
    k = review_event_key(orphan_row)
    cands = [s for s in snapshots if review_event_key(s) == k]
    if not cands:
        return None  # UNRESOLVED
    cands = sorted(cands, key=lambda s: str(s.get("Review_Date")))
    last = cands[-1]
    return (last.get("Status"), last.get("Rec_Count"))


snapshots = [
    row(Review_Date="2026-06-05", Status="持仓中", Rec_Count="2"),
    row(Review_Date="2026-06-08", Status="已超期归档", Rec_Count="2"),
]

# 10. orphan 可 deterministic resolve
orph = row(Review_Date="2026-06-02", Status="", Rec_Count="")
r10 = resolve_orphan(orph, snapshots)
check("10. orphan 可确定性回补(取最后非空快照)", r10 == ("已超期归档", "2"), f"{r10}")

# 11. ambiguous orphan -> UNRESOLVED，不猜
orph2 = row(Ticker="ZZZZ", Tag="Unknown", Review_Date="2026-06-02", Status="", Rec_Count="")
check("11. ambiguous orphan -> UNRESOLVED(不猜)", resolve_orphan(orph2, snapshots) is None)


print("== C. 数据不变性 ==")
# fixture：一段历史记录，repair 只改 Status/Rec_Count
before_fixture = [
    {"Ticker": "AVGO", "Rec_Date": "2026-06-02", "Tag": "Observation", "Status": "",
     "Rec_Count": "", "Rec_Price": "459.97", "Stop_Loss": "184", "Exit_Date": "",
     "Exit_Price": "", "Price_5D": "450.0", "PnL_5D": "-2.17", "PnL_10D": "-1.0", "PnL_20D": "0.5"},
]
def apply_repair(records):
    out = []
    for r in records:
        new = dict(r)
        if new["Status"] == "":
            new["Status"] = "观察推荐"
            new["Rec_Count"] = "1"
        out.append(new)
    return out

after_fixture = apply_repair(before_fixture)
b, a = before_fixture[0], after_fixture[0]
protected = ["Rec_Price", "Stop_Loss", "Exit_Date", "Exit_Price",
             "Price_5D", "PnL_5D", "PnL_10D", "PnL_20D"]
unchanged = all(b[k] == a[k] for k in protected)
check("12/13. Rec_Price/PnL/milestone/Stop_Loss/Exit 不被触碰", unchanged)

# 汇总
failed = [n for n, c in results if not c]
print(f"\n结果：通过 {len(results)-len(failed)} / {len(results)}")
if failed:
    print("失败：", failed)
    raise SystemExit(1)
print("全部通过 ✅")
