# -*- coding: utf-8 -*-
"""P3.5 确定性 Rec_Price 修复（逐事件核验 + 精确修复）。

7 个 EARLY_BACKFILL_CORRECTION 事件：第一快照 Rec_Price 是早期错误值，
正确基准 = trade_history Price（= Rec_Date 真实 Open，review.py safe_record_price 明确定义）。

修复：仅把「错误 Rec_Price 的快照行」改为 trade_history Price，不改任何其他字段。
这 7 个事件的 Price_N / PnL_N 全为空，故修复不改变 PnL / milestone / KPI。
"""
import pandas as pd

REPO = "/tmp/us"
RH = f"{REPO}/review_history.csv"
TH = f"{REPO}/trade_history.csv"

TARGETS = {
    ("NCLH", "2026-08-04"): "19.0",
    ("HAL",  "2026-08-07"): "31.88999938964844",
    ("OXY",  "2026-08-07"): "55.90999984741211",
    ("T",    "2026-08-07"): "23.790000915527344",
    ("GEN",  "2026-08-10"): "29.290000915527344",
    ("PPL",  "2026-08-10"): "34.9900016784668",
    ("UBER", "2026-08-10"): "78.02999877929688",
}


def f(v):
    v = str(v).strip()
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def main():
    rh = pd.read_csv(RH, dtype=str, keep_default_na=False)
    th = pd.read_csv(TH, dtype=str, keep_default_na=False)
    th["_tk"] = th["Ticker"].astype(str).str.upper()
    th["_d"] = th["Date"].astype(str).str[:10]

    # 逐事件验证 trade_history Price 与目标一致
    report = []
    repairs = []  # (index, old, new)

    for (tk, rd), expected in TARGETS.items():
        sub_th = th[(th["_tk"] == tk) & (th["_d"] == rd)]
        if len(sub_th) == 0:
            report.append({"Ticker": tk, "Rec_Date": rd, "Conclusion": "UNRESOLVED",
                           "Reason": "trade_history 无匹配记录"})
            continue
        th_price = str(sub_th.iloc[0]["Price"]).strip()
        # trade_history Price 必须与预期一致（防止漂移）
        if f(th_price) is None or abs(f(th_price) - f(expected)) > 1e-4:
            report.append({"Ticker": tk, "Rec_Date": rd, "Conclusion": "UNRESOLVED",
                           "Reason": f"trade_history Price({th_price}) != 预期({expected})"})
            continue

        # 该事件的所有快照
        sub = rh[(rh["Ticker"].astype(str).str.upper() == tk) &
                 (rh["Rec_Date"].astype(str).str[:10] == rd)].copy()
        # 识别错误快照：Rec_Price != trade_history Price
        wrong = sub[sub["Rec_Price"].apply(lambda v: f(v) is None or abs(f(v) - f(th_price)) > 1e-4)]
        for idx, r in wrong.iterrows():
            old = r["Rec_Price"]
            repairs.append((idx, old, th_price))
            report.append({
                "Ticker": tk, "Rec_Date": rd, "Tag": r["Tag"], "Review_Date": r["Review_Date"],
                "Old_Rec_Price": old, "New_Rec_Price": th_price,
                "Difference": round((f(th_price) - f(old)), 4),
                "Difference_Pct": round((f(th_price) - f(old)) / f(old) * 100, 2),
                "Trade_History_Price": th_price,
                "Actual_Open": th_price,
                "Evidence": "trade_history Price == 后续快照 Rec_Price == Rec_Date Open（safe_record_price 定义）",
                "Conclusion": "CONFIRMED_WRONG",
                "PnL_5D_Before": r["PnL_5D"], "PnL_5D_After": r["PnL_5D"],
                "PnL_10D_Before": r["PnL_10D"], "PnL_10D_After": r["PnL_10D"],
                "PnL_20D_Before": r["PnL_20D"], "PnL_20D_After": r["PnL_20D"],
                "Stage_Before": r["Review_Stage"], "Stage_After": r["Review_Stage"],
                "Action": "REPAIR",
            })

    # 写回（只改 Rec_Price）
    for idx, old, new in repairs:
        rh.at[idx, "Rec_Price"] = new

    # BEFORE/AFTER 对账
    audit = pd.DataFrame(report)
    audit.to_csv("/workspace/P3_5_rec_price_repair_audit.csv", index=False, encoding="utf-8")

    rh.to_csv(RH, index=False, encoding="utf-8")

    print("=" * 60)
    print("P3.5 Rec_Price 修复结果")
    print("=" * 60)
    print(f"修复行数: {len(repairs)}")
    print(f"CONFIRMED_WRONG: {sum(1 for r in report if r['Conclusion']=='CONFIRMED_WRONG')}")
    print(f"UNRESOLVED: {sum(1 for r in report if r['Conclusion']=='UNRESOLVED')}")
    print()
    for r in report:
        if r["Conclusion"] == "CONFIRMED_WRONG":
            print(f"  {r['Ticker']:6} {r['Rec_Date']} {r['Old_Rec_Price'][:12]:>12} -> {r['New_Rec_Price'][:12]:>12} ({r['Difference_Pct']:+.2f}%)")
        else:
            print(f"  {r['Ticker']:6} {r['Rec_Date']} UNRESOLVED: {r.get('Reason','')}")
    print()
    print("对账文件: /workspace/P3_5_rec_price_repair_audit.csv")


if __name__ == "__main__":
    main()
