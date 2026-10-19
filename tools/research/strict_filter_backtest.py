#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""严筛参数组合模拟（输入改用 quant_factor_backtest.csv，含前瞻收益）。

若某 Scan_Date 的 Forward_Return_* 全为空 ⇒ 该日不可回测（数据边界）。
输出 docs/STRICT_FILTER_BACKTEST.md（覆盖此前全 nan 版本）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
BT = REPO / "quant_factor_backtest.csv"
OUT = REPO / "docs" / "STRICT_FILTER_BACKTEST.md"

HORIZONS = (5, 10, 20)
STOP_PCT = 0.05
MAX_CAND = 3


def main() -> int:
    if not BT.exists():
        raise SystemExit("missing quant_factor_backtest.csv")
    d = pd.read_csv(BT, dtype=str, keep_default_na=False)
    for c in ("Price", "Quant_Score") + tuple(f"Forward_Return_{h}D" for h in HORIZONS):
        d[c] = pd.to_numeric(d[c].replace("", np.nan), errors="coerce")
    d["Scan_Date"] = pd.to_datetime(d["Scan_Date"], errors="coerce")
    d = d.dropna(subset=["Scan_Date", "Price"])

    cov = d.groupby(d["Scan_Date"].dt.date)[
        [f"Forward_Return_{h}D" for h in HORIZONS]].count()
    print("=== 前瞻收益覆盖（按 Scan_Date）===")
    print(cov.to_string())
    total20 = int(d["Forward_Return_20D"].notna().sum())
    print(f"\n  非空合计：5D={int(d['Forward_Return_5D'].notna().sum())} "
          f"10D={int(d['Forward_Return_10D'].notna().sum())} 20D={total20}")

    if total20 == 0:
        L = ["# 严筛参数组合模拟回测（数据边界阻塞）\n",
             "> 脚本：`tools/research/strict_filter_backtest.py`",
             f"> 输入：`{BT.name}`（**{len(d)}** 行 / **{d['Scan_Date'].nunique()}** 个 Scan_Date）\n",
             "## 结论：**无法回测** ✗\n",
             "`Forward_Return_5D/10D/20D` 在全部 Scan_Date 上**均为空**：",
             "价格数据最新只到 **2026-10-15**，而最早 Scan_Date 是 **2026-10-07**，",
             "前瞻 5/10/20 交易日全部超出数据边界。\n",
             "### 覆盖表\n",
             "| Scan_Date | 行数 | 5D 非空 | 10D 非空 | 20D 非空 |",
             "|---|---|---|---|---|"]
        for dt, row in cov.iterrows():
            n = int((d["Scan_Date"].dt.date == dt).sum())
            L.append(f"| {dt} | {n} | {int(row.iloc[0])} | {int(row.iloc[1])} | {int(row.iloc[2])} |")
        L += ["", "### 通过率（可算，与收益无关）\n",
              "| 组合 | MIN_SCORE | MIN_RR | target | 选出票数 |", "|---|---|---|---|---|"]
        for cid, ms, rr, mode in (("C1", 80, 2.0, "high20"), ("C2", 75, 2.0, "high20"),
                                  ("C3", 71, 2.0, "high20"), ("C4", 80, 2.0, "virtual"),
                                  ("C5", 75, 1.0, "high20"), ("C6", 71, 0.5, "high20"),
                                  ("C7", 75, 1.0, "virtual")):
            n = 0
            for _, day in d.groupby("Scan_Date"):
                used, cand = set(), []
                for _, r in day.iterrows():
                    if pd.isna(r["Quant_Score"]) or r["Quant_Score"] < ms:
                        continue
                    price = r["Price"]
                    if pd.isna(price) or price <= 0:
                        continue
                    stop = price * (1 - STOP_PCT)
                    if mode == "high20":
                        tgt = price * 1.0
                        if not pd.isna(r.get("MA20")):
                            tgt = max(price, float(r["MA20"])) if False else price
                        tgt = np.nan
                        cand_ok = False
                    else:
                        tgt = price + 2 * (price - stop)
                        cand_ok = True
                    if not cand_ok:
                        continue
                    rr_v = (tgt - price) / (price - stop)
                    if rr_v < rr:
                        continue
                    sec = (r.get("Sector") or "").strip()
                    if sec and sec in used:
                        continue
                    if sec:
                        used.add(sec)
                    cand.append(r)
                cand.sort(key=lambda x: -x["Quant_Score"])
                n += len(cand[:MAX_CAND])
            L.append(f"| {cid} | {ms} | {rr} | {mode} | **{n}** |")
        L += ["", "> `high20` 模式在 `quant_factor_backtest.csv` 中**没有 20 日高点列**（该文件不含 `High20`）",
              "> ⇒ 无法复现 `target = 20 日高点`；仅 `virtual` 模式可算。\n",
              "## 数据边界说明\n",
              f"- `quant_factor_backtest.csv`：**{len(d)}** 行、Scan_Date **{d['Scan_Date'].min().date()} ~ "
              f"{d['Scan_Date'].max().date()}**",
              "- 前瞻收益列为空的原因：价格历史 `quant_factor_price_history.csv` 只到 **2026-10-15** ✗",
              "- **需等 20 个交易日**（约 11 月中旬）才能回测这 9 个截面 ✓",
              "- 或改用 **2y PIT**（`research_factor_snapshots_sp500_pit_2y.csv` + "
              "`research_backtest_sp500_pit_2y.csv`，**已含 Forward_Return_*** ✓，但**无 Quant_Score** ✗）",
              ""]
        OUT.write_text("\n".join(L), encoding="utf-8")
        print(f"\nwritten: {OUT} ({OUT.stat().st_size} bytes)")
        return 0

    print("\n  ⇒ 有前瞻收益，可继续完整回测（下一轮实现）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
