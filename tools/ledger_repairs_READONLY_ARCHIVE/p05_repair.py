# -*- coding: utf-8 -*-
"""P0.5 Stop_Loss 历史数据定点修复（deterministic、一次性、可重复验证）。

严格只修改已审计出的 15 条异常记录，fail-closed：
  - 目标行唯一性校验（0 行或 >1 行 -> 停止，不写数据）；
  - 字段与 repair report 不一致 -> 停止。

修复规则：
  ① 历史技术指标（MA20/MA50/ATR_Pct）可确定 -> 用历史技术止损（本批 15 条均无，故不适用）；
  ② repair report 来源 ticker 可确定原始正确值 -> 本批均为“跨ticker污染”，无正确来源值；
  ③ fallback = Rec_Price × 0.95（scan 默认 5%，非 3%）。

运行：python3 p05_repair.py  （工作目录 /tmp/us）
输出：/workspace/P0.5_stop_loss_repair_before.csv
      /workspace/P0.5_stop_loss_repair_after.csv
      /workspace/P0.5_stop_loss_before_after.csv
      并就地写回 trade_history.csv / review_history.csv
"""
import os
import sys
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd

WORKSPACE = "/tmp/us"
OUTDIR = "/workspace"

TH = os.path.join(WORKSPACE, "trade_history.csv")
RH = os.path.join(WORKSPACE, "review_history.csv")


def _num(v):
    s = str(v).strip().replace("$", "").replace(",", "")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _fallback_stop(rec_price):
    """Rec_Price × 0.95，量化到 2 位小数（ROUND_HALF_UP），返回字符串。"""
    d = Decimal(str(rec_price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    v = (d * Decimal("0.95")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{v:.2f}"


# ---------------------------------------------------------------------------
# 目标集合（唯一来源：repair report 已识别的 15 条）
# (Ticker, Rec_Date, bad_stop_float)
# ---------------------------------------------------------------------------
TARGETS = [
    ("GRAB", "2026-06-03", 34.80),
    ("RIVN", "2026-06-03", 34.80),
    ("SRXH", "2026-06-05", 4.20),
    ("NOTV", "2026-06-09", 105.00),
    ("F",    "2026-06-19", 965.00),
    ("HOOD", "2026-06-19", 965.00),
    ("MSTR", "2026-06-19", 965.00),
    ("PFE",  "2026-06-19", 965.00),
    ("ACN",  "2026-06-22", 395.00),
    ("PFE",  "2026-06-22", 395.00),
    ("PLTR", "2026-06-22", 395.00),
    ("BSX",  "2026-06-25", 980.00),
    ("HAL",  "2026-06-25", 980.00),
    ("PFE",  "2026-06-25", 980.00),
    ("ORCL", "2026-06-26", 505.00),
]

# 3 条错误触发记录（撤销 STOP_TRIGGERED）
TRIGGERED = {("MSTR", "2026-06-19"), ("BSX", "2026-06-25"), ("ORCL", "2026-06-26")}

# ---------------------------------------------------------------------------
# 读取
# ---------------------------------------------------------------------------
th = pd.read_csv(TH, dtype=str, keep_default_na=False)
rh = pd.read_csv(RH, dtype=str, keep_default_na=False)

th["_tk"] = th["Ticker"].astype(str).str.upper()
th["_dt"] = th["Date"].astype(str).str[:10]
th["_stop_num"] = th["Stop_Loss"].apply(_num)

rh["_tk"] = rh["Ticker"].astype(str).str.upper()
rh["_rd"] = rh["Rec_Date"].astype(str).str[:10]
rh["_stop_num"] = rh["Stop_Loss"].apply(_num)

# Rec_Price 基价（优先 review_history 的有效 Rec_Price，否则 trade_history Price）
def _base_price(tk, rd, th_row):
    m = rh[(rh["_tk"] == tk) & (rh["_rd"] == rd)]
    if not m.empty:
        rp = _num(m.iloc[0].get("Rec_Price"))
        if rp and rp > 0:
            return rp
    p = _num(th_row.get("Price"))
    return p if p and p > 0 else None


# ---------------------------------------------------------------------------
# 校验 + 生成 BEFORE 快照
# ---------------------------------------------------------------------------
before_rows = []
failures = []

for tk, rd, bad in TARGETS:
    m = th[(th["_tk"] == tk) & (th["_dt"] == rd) & (th["_stop_num"] == bad)]
    if len(m) != 1:
        failures.append(f"trade_history 目标 {tk}/{rd}/stop={bad} 匹配 {len(m)} 行（应=1）")
        continue
    row = m.iloc[0]
    base = _base_price(tk, rd, row)
    if base is None:
        failures.append(f"{tk}/{rd} 无法确定 Rec_Price，FAIL CLOSED")
        continue
    new_stop = _fallback_stop(base)
    before_rows.append({
        "Ticker": tk, "Rec_Date": rd, "Rec_Price": _num(row.get("Price")),
        "Recorded_Price": row.get("Price"), "Stop_Loss": row.get("Stop_Loss"),
        "Status": row.get("Status"), "Exit_Date": row.get("Exit_Date"),
        "Exit_Price": row.get("Exit_Price"), "Stop_Method": row.get("Stop_Method"),
        "Trail_Stop": row.get("Trail_Stop"), "MA20": row.get("MA20"),
        "MA50": row.get("MA50"), "ATR_Pct": row.get("ATR_Pct"),
        "Score": row.get("Score"), "Review_Risk_Status": row.get("Review_Risk_Status"),
        "Review_Risk_Date": row.get("Review_Risk_Date"), "Date": row.get("Date"),
        "_new_stop": new_stop, "_base": base,
    })

if failures:
    print("FAIL CLOSED — 存在不满足条件的记录：")
    for f in failures:
        print("  ❌", f)
    sys.exit(1)

print(f"✅ 15 条目标记录全部唯一命中；技术指标均缺失 -> 修复来源 = fallback_5pct (Rec_Price × 0.95)")

# ---------------------------------------------------------------------------
# 生成 BEFORE 快照
# ---------------------------------------------------------------------------
before_df = pd.DataFrame(before_rows)
before_cols = [c for c in ["Ticker","Rec_Date","Rec_Price","Recorded_Price","Stop_Loss","Status",
                           "Exit_Date","Exit_Price","Stop_Method","Trail_Stop","MA20","MA50","ATR_Pct",
                           "Score","Review_Risk_Status","Review_Risk_Date","Date"] if c in before_df.columns]
before_df[before_cols].to_csv(os.path.join(OUTDIR, "P0.5_stop_loss_repair_before.csv"), index=False, encoding="utf-8")

# ---------------------------------------------------------------------------
# 执行修复
# ---------------------------------------------------------------------------
# 先记录 review_history 中 3 条错误触发记录 09-29 行的前一行（用于 Status/Review_Stage 回退）
prev_state = {}
for tk, rd in TRIGGERED:
    sub = rh[(rh["_tk"] == tk) & (rh["_rd"] == rd)].sort_values("Review_Date")
    trig = sub[sub["Status"].astype(str).str.strip() == "移动止损清仓"]
    if len(trig) != 1:
        failures.append(f"review_history {tk}/{rd} '移动止损清仓' 行匹配 {len(trig)} 行（应=1）")
        continue
    idx_list = list(sub.index)
    ti = list(trig.index)[0]
    pos = idx_list.index(ti)
    if pos == 0:
        failures.append(f"review_history {tk}/{rd} '移动止损清仓' 行之前无前一行，无法回退")
        continue
    prev = sub.loc[idx_list[pos - 1]]
    prev_state[(tk, rd)] = (prev.get("Status"), prev.get("Review_Stage"))

if len(prev_state) != 3 or failures:
    print("FAIL CLOSED — review_history 3 条错误触发回退校验失败：")
    for f in failures:
        print("  ❌", f)
    sys.exit(1)

# --- trade_history：15 条 Stop_Loss 修复 + 3 条状态回退 ---
th_changed = 0
for tk, rd, bad in TARGETS:
    m = th[(th["_tk"] == tk) & (th["_dt"] == rd) & (th["_stop_num"] == bad)]
    row = m.iloc[0]
    base = _base_price(tk, rd, row)
    new_stop = _fallback_stop(base)
    idx = m.index[0]
    th.at[idx, "Stop_Loss"] = new_stop
    th_changed += 1
    if (tk, rd) in TRIGGERED:
        # 撤销 STOP_TRIGGERED 的退出字段与触发派生字段
        th.at[idx, "Status"] = "Active"
        th.at[idx, "Exit_Date"] = ""
        th.at[idx, "Exit_Price"] = ""
        th.at[idx, "Review_Risk_Status"] = ""
        th.at[idx, "Review_Risk_Date"] = ""
        if "Review_Stop_Distance_Pct" in th.columns:
            th.at[idx, "Review_Stop_Distance_Pct"] = ""
        if "Review_Risk_Note" in th.columns:
            th.at[idx, "Review_Risk_Note"] = ""

# --- review_history：所有含错误 Stop 的行修复 Stop_Loss；3 条错误触发的 09-29 行回退状态 ---
rh_changed_stop = 0
rh_changed_state = 0
for tk, rd, bad in TARGETS:
    m = rh[(rh["_tk"] == tk) & (rh["_rd"] == rd) & (rh["_stop_num"] == bad)]
    th_row = th[(th["_tk"] == tk) & (th["_dt"] == rd)].iloc[0]
    base = _base_price(tk, rd, th_row)
    new_stop = _fallback_stop(base)
    for idx in m.index:
        rh.at[idx, "Stop_Loss"] = new_stop
        rh_changed_stop += 1
    if (tk, rd) in TRIGGERED:
        trig = rh[(rh["_tk"] == tk) & (rh["_rd"] == rd) &
                  (rh["Status"].astype(str).str.strip() == "移动止损清仓")]
        for idx in trig.index:
            ps, pr = prev_state[(tk, rd)]
            rh.at[idx, "Status"] = ps
            rh.at[idx, "Review_Stage"] = pr
            # 清空触发派生字段
            for _c in ("Review_Risk_Status", "Review_Risk_Date", "Review_Stop_Distance_Pct", "Review_Risk_Note"):
                if _c in rh.columns:
                    rh.at[idx, _c] = ""
            rh_changed_state += 1

# ---------------------------------------------------------------------------
# 写回
# ---------------------------------------------------------------------------
th.drop(columns=["_tk", "_dt", "_stop_num"]).to_csv(TH, index=False, encoding="utf-8")
rh.drop(columns=["_tk", "_rd", "_stop_num"]).to_csv(RH, index=False, encoding="utf-8")

print(f"✅ trade_history 修复 Stop_Loss: {th_changed} 行（含 3 条状态回退）")
print(f"✅ review_history 修复 Stop_Loss: {rh_changed_stop} 行；状态回退: {rh_changed_state} 行")

# ---------------------------------------------------------------------------
# AFTER 快照 + BEFORE-AFTER 对账（重新读盘生成）
# ---------------------------------------------------------------------------

th2 = pd.read_csv(TH, dtype=str, keep_default_na=False)
rh2 = pd.read_csv(RH, dtype=str, keep_default_na=False)
th2["_tk"] = th2["Ticker"].astype(str).str.upper(); th2["_dt"] = th2["Date"].astype(str).str[:10]
th2["_stop_num"] = th2["Stop_Loss"].apply(_num)

after_rows = []
for tk, rd, bad in TARGETS:
    m = th2[(th2["_tk"] == tk) & (th2["_dt"] == rd)]
    # 取该 ticker+date 的（可能多行）中 Stop_Loss 已被修复的那一行
    rows = m[m["_stop_num"].notna() & (m["_stop_num"] != bad)]
    if rows.empty:
        rows = m
    r = rows.iloc[0]
    after_rows.append({
        "Ticker": tk, "Rec_Date": rd, "Stop_Loss": r.get("Stop_Loss"),
        "Status": r.get("Status"), "Exit_Date": r.get("Exit_Date"),
        "Exit_Price": r.get("Exit_Price"),
    })

after_df = pd.DataFrame(after_rows)
after_df.to_csv(os.path.join(OUTDIR, "P0.5_stop_loss_repair_after.csv"), index=False, encoding="utf-8")

ba_rows = []
for (b, a) in zip(before_rows, after_rows):
    tk = b["Ticker"]; rd = b["Rec_Date"]
    is_trig = (tk, rd) in TRIGGERED
    ba_rows.append({
        "Ticker": tk, "Rec_Date": rd,
        "Old_Stop_Loss": b["Stop_Loss"], "New_Stop_Loss": a["Stop_Loss"],
        "Old_Status": b["Status"], "New_Status": a["Status"],
        "Old_Exit_Date": b["Exit_Date"], "New_Exit_Date": a["Exit_Date"],
        "Old_Exit_Price": b["Exit_Price"], "New_Exit_Price": a["Exit_Price"],
        "Repair_Reason": "data_error_trigger_rollback" if is_trig else "closed_lifecycle_stop_fix",
        "Repair_Source": "fallback_5pct",
        "Was_Stop_Triggered_By_Bad_Data": "YES" if is_trig else "NO",
    })

ba_df = pd.DataFrame(ba_rows)
ba_df.to_csv(os.path.join(OUTDIR, "P0.5_stop_loss_before_after.csv"), index=False, encoding="utf-8")

print("\n=== 修复汇总（BEFORE → AFTER）===")
print(ba_df.to_string(index=False))
print("\n✅ 修复完成，3 个输出文件已写入 /workspace")
