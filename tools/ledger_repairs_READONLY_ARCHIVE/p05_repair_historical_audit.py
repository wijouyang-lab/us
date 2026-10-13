# -*- coding: utf-8 -*-
"""P0.5 历史数据修复验证测试（确定性，对比 HEAD 与工作区）。

验证 12 项：
  1. 15 条目标记录全部命中且唯一
  2. 非目标记录 0 条变化
  3. 12 条结束记录 Status 不变
  4. 12 条结束记录 Exit_Date 不变
  5. 12 条结束记录 Exit_Price 不变
  6. 三条 MSTR/BSX/ORCL 的错误 STOP_TRIGGERED 被恢复
  7. 三条新 Stop_Loss 不再使用 965/980/505
  8. 所有 New_Stop_Loss finite/positive
  9. Rec_Price 0 条变化
  10. milestone (Price_5D/10D/20D) 0 条变化
  11. PnL_5D/10D/20D 0 条变化
  12. 非目标 ticker 0 条变化
"""
import subprocess
import pandas as pd

def _num(v):
    s = str(v).strip().replace("$", "").replace(",", "")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None

# before = HEAD（d522724），after = 工作区
def git_show(path):
    return subprocess.check_output(["git", "show", f"HEAD:{path}"]).decode("utf-8")

import io
th_b = pd.read_csv(io.StringIO(git_show("trade_history.csv")), dtype=str, keep_default_na=False)
rh_b = pd.read_csv(io.StringIO(git_show("review_history.csv")), dtype=str, keep_default_na=False)
th_a = pd.read_csv("trade_history.csv", dtype=str, keep_default_na=False)
rh_a = pd.read_csv("review_history.csv", dtype=str, keep_default_na=False)

TARGETS = [
    ("GRAB","2026-06-03",34.80),("RIVN","2026-06-03",34.80),("SRXH","2026-06-05",4.20),
    ("NOTV","2026-06-09",105.00),("F","2026-06-19",965.00),("HOOD","2026-06-19",965.00),
    ("MSTR","2026-06-19",965.00),("PFE","2026-06-19",965.00),("ACN","2026-06-22",395.00),
    ("PFE","2026-06-22",395.00),("PLTR","2026-06-22",395.00),("BSX","2026-06-25",980.00),
    ("HAL","2026-06-25",980.00),("PFE","2026-06-25",980.00),("ORCL","2026-06-26",505.00),
]
TRIGGERED = {("MSTR","2026-06-19"),("BSX","2026-06-25"),("ORCL","2026-06-26")}

def th_key(df):
    df = df.copy()
    df["_k"] = df["Ticker"].str.upper() + "|" + df["Date"].astype(str).str[:10]
    return df

results = []
def check(name, cond, detail=""):
    results.append((name, cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""))

# 1. 15 条目标在 before 中唯一命中（含 bad stop）
print("== 1. 目标命中唯一性 ==")
for tk, rd, bad in TARGETS:
    m = th_b[(th_b["Ticker"].str.upper()==tk)&(th_b["Date"].astype(str).str[:10]==rd)&(th_b["Stop_Loss"].apply(_num)==bad)]
    check(f"{tk}/{rd} before 唯一命中", len(m)==1, f"{len(m)} 行")

# 2 & 12. 非目标记录 0 变化：比较 before/after 逐行，定位变化行集合
print("== 2/12. 非目标记录变化 ==")
thb_k = th_key(th_b).set_index("_k"); tha_k = th_key(th_a).set_index("_k")
changed_rows = []
for k in thb_k.index:
    if not thb_k.loc[k].equals(tha_k.loc[k]):
        tk = k.split("|")[0]; rd = k.split("|")[1]
        changed_rows.append((tk, rd))
target_keys = {(tk, rd) for tk, rd, _ in TARGETS}
non_target_changed = [c for c in changed_rows if c not in target_keys]
check("非目标 trade_history 行 0 变化", len(non_target_changed)==0, f"{len(non_target_changed)} 行")

# 3/4/5. 12 条结束记录 Status/Exit_Date/Exit_Price 不变
print("== 3/4/5. 12 条结束记录状态字段不变 ==")
closed = [t for t in TARGETS if (t[0], t[1]) not in TRIGGERED]
bad_status = bad_exitd = bad_exitp = 0
for tk, rd, bad in closed:
    b = th_b[(th_b["Ticker"].str.upper()==tk)&(th_b["Date"].astype(str).str[:10]==rd)&(th_b["Stop_Loss"].apply(_num)==bad)].iloc[0]
    a = th_a[(th_a["Ticker"].str.upper()==tk)&(th_a["Date"].astype(str).str[:10]==rd)].iloc[0]
    if b["Status"] != a["Status"]: bad_status += 1
    if b["Exit_Date"] != a["Exit_Date"]: bad_exitd += 1
    if b["Exit_Price"] != a["Exit_Price"]: bad_exitp += 1
check("12 条 Status 不变", bad_status==0, f"{bad_status} 变化")
check("12 条 Exit_Date 不变", bad_exitd==0, f"{bad_exitd} 变化")
check("12 条 Exit_Price 不变", bad_exitp==0, f"{bad_exitp} 变化")

# 6. 三条错误触发恢复为 Active，Exit 清空
print("== 6. 三条错误触发回退 ==")
for tk, rd in TRIGGERED:
    a = th_a[(th_a["Ticker"].str.upper()==tk)&(th_a["Date"].astype(str).str[:10]==rd)].iloc[0]
    ok = (a["Status"]=="Active") and (a["Exit_Date"]=="") and (a["Exit_Price"]=="") and (a["Review_Risk_Status"]=="")
    check(f"{tk}/{rd} 恢复 Active 且 Exit 清空", bool(ok), f"Status={a['Status']} Exit_Date={a['Exit_Date']}")

# 7. 三条新 Stop 不再使用 965/980/505
print("== 7. 三条新 Stop 不再使用异常值 ==")
for tk, rd in TRIGGERED:
    a = th_a[(th_a["Ticker"].str.upper()==tk)&(th_a["Date"].astype(str).str[:10]==rd)].iloc[0]
    v = _num(a["Stop_Loss"])
    check(f"{tk}/{rd} 新 Stop={a['Stop_Loss']} 非 965/980/505", v not in (965,980,505))

# 8. 所有 New_Stop_Loss finite/positive
print("== 8. 新 Stop 全部 finite/positive ==")
all_ok = True
for tk, rd, bad in TARGETS:
    a = th_a[(th_a["Ticker"].str.upper()==tk)&(th_a["Date"].astype(str).str[:10]==rd)]
    # 取被修复的那行（Stop != bad 且非 N/A）
    a2 = a[(a["Stop_Loss"].apply(_num).notna()) & (a["Stop_Loss"].apply(_num) != bad)]
    if a2.empty:
        all_ok = False; continue
    v = _num(a2.iloc[0]["Stop_Loss"])
    if v is None or not (v > 0 and v == v and v not in (float("inf"), float("-inf"))):
        all_ok = False
check("15 条新 Stop 全部 finite 正数", all_ok)

# 9. Rec_Price 0 变化
print("== 9. Rec_Price 0 变化 ==")
rhb_k = rh_b.copy(); rha_k = rh_a.copy()
rhb_k["_k"] = rhb_k["Ticker"].str.upper()+"|"+rhb_k["Rec_Date"].astype(str).str[:10]+"|"+rhb_k["Review_Date"].astype(str).str[:10]
rha_k["_k"] = rha_k["Ticker"].str.upper()+"|"+rha_k["Rec_Date"].astype(str).str[:10]+"|"+rha_k["Review_Date"].astype(str).str[:10]
rec_price_changed = 0
for k in rhb_k["_k"]:
    b = rhb_k[rhb_k["_k"]==k].iloc[0]; a = rha_k[rha_k["_k"]==k].iloc[0]
    if b["Rec_Price"] != a["Rec_Price"]:
        rec_price_changed += 1
check("Rec_Price 0 变化", rec_price_changed==0, f"{rec_price_changed} 变化")

# 10. milestone Price_5D/10D/20D 0 变化
print("== 10. milestone 0 变化 ==")
mil_changed = 0
for col in ["Price_5D","Price_10D","Price_20D"]:
    if col in rh_b.columns:
        for k in rhb_k["_k"]:
            b = rhb_k[rhb_k["_k"]==k].iloc[0]; a = rha_k[rha_k["_k"]==k].iloc[0]
            if b[col] != a[col]: mil_changed += 1
check("Price_5D/10D/20D 0 变化", mil_changed==0, f"{mil_changed} 变化")

# 11. PnL 0 变化
print("== 11. PnL 0 变化 ==")
pnl_changed = 0
for col in ["PnL_5D","PnL_10D","PnL_20D","Maturity_PnL"]:
    if col in rh_b.columns:
        for k in rhb_k["_k"]:
            b = rhb_k[rhb_k["_k"]==k].iloc[0]; a = rha_k[rha_k["_k"]==k].iloc[0]
            if b[col] != a[col]: pnl_changed += 1
check("PnL_5D/10D/20D 0 变化", pnl_changed==0, f"{pnl_changed} 变化")

# 汇总
failed = [n for n, c in results if not c]
print(f"\n结果：通过 {len(results)-len(failed)} / {len(results)}")
if failed:
    print("失败：", failed)
    raise SystemExit(1)
print("全部通过 ✅")
