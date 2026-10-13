# -*- coding: utf-8 -*-
"""P2 数据修复：review_event_key 对账 + orphan records 确定性回补。

只做两件事：
  1. 对 review_history.csv 每行计算 Old_review_event_key / New_review_event_key（对账，不改数据）；
  2. 对 orphan（Status 空）行，若能通过「同 (Rec_Date,Ticker,Tag) 的最后一条非空快照」确定性回补，
     则回补 Status / Rec_Count；否则标记 UNRESOLVED 保留原值。

边界：
  - 不改 Rec_Date / Ticker / Tag / Rec_Price / Stop_Loss / Exit_Date / Exit_Price
  - 不改 Price_5D/10D/20D / PnL_5D/10D/20D / Review_Stage
  - 不删除任何历史行
"""
import ast
import os

import pandas as pd

REPO = "/tmp/us"
REVIEW_HISTORY = os.path.join(REPO, "review_history.csv")
SRC = open(os.path.join(REPO, "review.py"), encoding="utf-8").read()

# 抽取 production 的 clean_text / INVALID_STRINGS / review_event_key（新）
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
new_event_key = _ns["review_event_key"]


def old_event_key(row):
    """旧 key 规则（修复前）：含 Review_Date 与 Status，缺 Tag。"""
    return (
        clean_text(row.get("Review_Date"))[:10],
        clean_text(row.get("Ticker")).upper(),
        clean_text(row.get("Rec_Date"))[:10],
        clean_text(row.get("Status")),
        clean_text(row.get("Option_Type")).upper(),
        clean_text(row.get("Strike")),
        clean_text(row.get("Expiry")),
    )


def main():
    rh = pd.read_csv(REVIEW_HISTORY, dtype=str, keep_default_na=False)
    n_total = len(rh)

    # 规范化辅助列
    rh["_rd"] = rh["Rec_Date"].astype(str).str[:10]
    rh["_tk"] = rh["Ticker"].astype(str).str.upper()
    rh["_tag"] = rh["Tag"].astype(str).str.strip()
    rh["_new_key"] = rh["Rec_Date"] + "|" + rh["_tk"] + "|" + rh["_tag"] + "|" + \
        rh["Option_Type"].astype(str).str.upper() + "|" + rh["Strike"] + "|" + rh["Expiry"]

    # 旧/新 key 逐行（用于对账，元组 -> 字符串）
    old_keys = [old_event_key(r) for _, r in rh.iterrows()]
    new_keys = [new_event_key(r) for _, r in rh.iterrows()]

    # ---- orphan 识别与回补 ----
    is_orph = rh["Status"].astype(str).str.strip().eq("")
    orph = rh[is_orph]
    non_orph = rh[~is_orph]

    # 每个 key 的最后一条非空快照（按 Review_Date 排序取最后）
    non_orph_sorted = non_orph.sort_values(["_new_key", "Review_Date"])
    last_non_orph = non_orph_sorted.groupby("_new_key").tail(1)
    lookup = {}
    for _, r in last_non_orph.iterrows():
        lookup[r["_new_key"]] = (r["Status"], r["Rec_Count"])

    repair_rows = []
    repair_report = []
    for i, r in orph.iterrows():
        key = r["_new_key"]
        old_st = r["Status"]
        old_rc = r["Rec_Count"]
        if key in lookup:
            st, rc = lookup[key]
            repair_rows.append((i, st, rc))
            repair_report.append({
                "Ticker": r["_tk"], "Rec_Date": r["_rd"], "Tag": r["_tag"],
                "Review_Date": r["Review_Date"],
                "Old_Status": old_st, "Old_Rec_Count": old_rc,
                "Old_review_event_key": "|".join(old_keys[i]),
                "Resolved_Event_Key": key,
                "Resolution_Method": "same_event_last_nonempty_snapshot",
                "Confidence": "HIGH",
                "Action": "REPAIR",
            })
        else:
            repair_report.append({
                "Ticker": r["_tk"], "Rec_Date": r["_rd"], "Tag": r["_tag"],
                "Review_Date": r["Review_Date"],
                "Old_Status": old_st, "Old_Rec_Count": old_rc,
                "Old_review_event_key": "|".join(old_keys[i]),
                "Resolved_Event_Key": "",
                "Resolution_Method": "",
                "Confidence": "LOW",
                "Action": "UNRESOLVED",
            })

    n_resolved = len(repair_rows)
    n_unresolved = len(orph) - n_resolved

    # ---- 写回（只改 Status / Rec_Count）----
    for i, st, rc in repair_rows:
        rh.at[i, "Status"] = st
        rh.at[i, "Rec_Count"] = rc

    # ---- 生成对账文件 ----
    # P2_orphan_before.csv
    before_cols = ["Ticker", "Rec_Date", "Tag", "Review_Date", "Status", "Rec_Count", "Rec_Price", "Review_Stage"]
    orph[before_cols].to_csv("/workspace/P2_orphan_before.csv", index=False, encoding="utf-8")

    # P2_orphan_repair_report.csv
    pd.DataFrame(repair_report).to_csv("/workspace/P2_orphan_repair_report.csv", index=False, encoding="utf-8")

    # P2_orphan_after.csv（从已修改的 rh 里取原 orphan 行）
    rh_after = rh.loc[orph.index, before_cols]
    rh_after.to_csv("/workspace/P2_orphan_after.csv", index=False, encoding="utf-8")

    # P2_event_key_before.csv / after.csv（全表逐行 key）
    ek_before = pd.DataFrame({
        "Record_ID": range(1, n_total + 1),
        "Ticker": rh["Ticker"], "Rec_Date": rh["Rec_Date"], "Tag": rh["Tag"],
        "Review_Date": rh["Review_Date"], "Status": rh["Status"],
        "Old_review_event_key": ["|".join(k) for k in old_keys],
    })
    ek_before.to_csv("/workspace/P2_event_key_before.csv", index=False, encoding="utf-8")

    ek_after = pd.DataFrame({
        "Record_ID": range(1, n_total + 1),
        "Ticker": rh["Ticker"], "Rec_Date": rh["Rec_Date"], "Tag": rh["Tag"],
        "New_review_event_key": ["|".join(k) for k in new_keys],
    })
    ek_after.to_csv("/workspace/P2_event_key_after.csv", index=False, encoding="utf-8")

    # P2_event_key_before_after.csv
    ba = pd.DataFrame({
        "Record_ID": range(1, n_total + 1),
        "Ticker": rh["Ticker"], "Rec_Date": rh["Rec_Date"], "Tag": rh["Tag"],
        "Old_key": ["|".join(k) for k in old_keys],
        "New_key": ["|".join(k) for k in new_keys],
        "Changed": ["N" if o == n else "Y" for o, n in zip(old_keys, new_keys)],
        "Reason": ["same_event_key" if o == n else "key_rule_changed" for o, n in zip(old_keys, new_keys)],
    })
    ba.to_csv("/workspace/P2_event_key_before_after.csv", index=False, encoding="utf-8")

    # P2_before_after.csv（orphan 行）
    p2ba_rows = []
    for idx, r in orph.iterrows():
        rep = next((x for x in repair_report if x["Ticker"] == r["_tk"] and x["Rec_Date"] == r["_rd"] and x["Review_Date"] == r["Review_Date"]), None)
        p2ba_rows.append({
            "Record_ID": idx + 1,
            "Ticker": r["_tk"], "Rec_Date": r["_rd"], "Tag": r["_tag"],
            "Old_event_key": "|".join(old_keys[idx]),
            "New_event_key": "|".join(new_keys[idx]),
            "Old_Status": rep["Old_Status"], "New_Status": rh.at[idx, "Status"],
            "Old_Rec_Count": rep["Old_Rec_Count"], "New_Rec_Count": rh.at[idx, "Rec_Count"],
            "Action": rep["Action"],
            "Reason": rep["Resolution_Method"] if rep["Action"] == "REPAIR" else "no_deterministic_lineage",
        })
    pd.DataFrame(p2ba_rows).to_csv("/workspace/P2_before_after.csv", index=False, encoding="utf-8")

    # ---- 写回 review_history.csv ----
    rh.drop(columns=["_rd", "_tk", "_tag", "_new_key"], inplace=True)
    rh.to_csv(REVIEW_HISTORY, index=False, encoding="utf-8")

    # ---- 统计输出 ----
    print("=" * 60)
    print("P2 数据修复结果")
    print("=" * 60)
    print(f"Total review rows        : {n_total}")
    print(f"Orphan (Status空) 总数   : {len(orph)}")
    print(f"  REPAIR (回补 Status/Rec_Count): {n_resolved} 行")
    print(f"  UNRESOLVED (保留空)           : {n_unresolved} 行")
    print("对账文件已写入 /workspace/:")
    for f in ["P2_orphan_before.csv", "P2_orphan_after.csv", "P2_orphan_repair_report.csv",
              "P2_event_key_before.csv", "P2_event_key_after.csv",
              "P2_event_key_before_after.csv", "P2_before_after.csv"]:
        print(f"  - {f}")


if __name__ == "__main__":
    main()
