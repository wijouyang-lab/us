#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2y PIT 行业轮动回测（市场中性化版）。

数据：research_backtest_sp500_pit_2y.csv（含 Forward_Return_5/10/20D）
      sp500_constituents.csv（Ticker -> Sector，PIT 行业漂移不可复现）
输出：docs/SECTOR_ROTATION_BACKTEST_2Y.md

方法：
  ① **超额收益**：个股前瞻收益 − 当日全市场平均前瞻收益（市场中性 ✓，剔除 beta）
  ② 行业动量：每日按 Sector 内 `Momentum_20D_Pct` 均值排序（该表无 Sector_RS 字段）
  ③ 取最强 3 / 最弱 3 行业，统计其成分股的**超额收益**
  ④ 多空 = 强 − 弱；按日序列算夏普
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
BT = REPO / "research_backtest_sp500_pit_2y.csv"
CONST = REPO / "sp500_constituents.csv"
OUT = REPO / "docs" / "SECTOR_ROTATION_BACKTEST_2Y.md"

TOP_N = 3
HORIZONS = (5, 10, 20)
MOM = "Momentum_20D_Pct"


def main() -> int:
    if not BT.exists():
        raise SystemExit(f"missing {BT}")
    d = pd.read_csv(BT, dtype=str, keep_default_na=False)
    for c in [MOM] + [f"Forward_Return_{h}D" for h in HORIZONS]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=[MOM])
    print(f"rows={len(d)} dates={d['Scan_Date'].nunique()}")

    sm = pd.read_csv(CONST, dtype=str)
    smap = {str(r["Ticker"]).strip().upper(): str(r.get("Sector") or "NA")
            for _, r in sm.iterrows()}
    d["Sector"] = d["Ticker"].astype(str).str.upper().map(smap).fillna("NA")
    print(f"  sectors={d['Sector'].nunique()} 覆盖={int((d['Sector'] != 'NA').sum())}/{len(d)}")

    # ---------- 超额收益（市场中性）----------
    for h in HORIZONS:
        d[f"Ex_{h}"] = d[f"Forward_Return_{h}D"] - d.groupby("Scan_Date")[
            f"Forward_Return_{h}D"].transform("mean")

    # ---------- 每日行业排名 + 分层 ----------
    daily = []          # (date, strong, weak)
    strong_rows, weak_rows = [], []
    for dt, day in d.groupby("Scan_Date"):
        g = day.groupby("Sector")[MOM].mean().sort_values(ascending=False)
        if len(g) < TOP_N * 2:
            continue
        strong, weak = list(g.index[:TOP_N]), list(g.index[-TOP_N:])
        daily.append((dt, strong, weak))
        strong_rows.append(day[day["Sector"].isin(strong)])
        weak_rows.append(day[day["Sector"].isin(weak)])

    if not daily:
        raise SystemExit("no usable dates")
    S = pd.concat(strong_rows)
    W = pd.concat(weak_rows)
    print(f"  usable dates={len(daily)} | strong rows={len(S)} weak rows={len(W)}")

    def st(df, h):
        v = pd.to_numeric(df[f"Ex_{h}"], errors="coerce").dropna()
        return dict(mean=float(v.mean()) * 100 if len(v) else np.nan,
                    win=float((v > 0).mean()) * 100 if len(v) else np.nan,
                    n=int(len(v)))

    # 多空：按日计算（强均值 − 弱均值）
    ls = {}
    for h in HORIZONS:
        rows = []
        for dt, strong, weak in daily:
            day = d[d["Scan_Date"] == dt]
            s = pd.to_numeric(day[day["Sector"].isin(strong)][f"Ex_{h}"], errors="coerce").mean()
            w = pd.to_numeric(day[day["Sector"].isin(weak)][f"Ex_{h}"], errors="coerce").mean()
            if pd.notna(s) and pd.notna(w):
                rows.append(s - w)
        arr = np.array(rows, dtype=float)
        sh = (arr.mean() / arr.std(ddof=1) * np.sqrt(252 / h)) if len(arr) > 2 and arr.std(ddof=1) > 0 else np.nan
        ls[h] = dict(mean=arr.mean() * 100 if len(arr) else np.nan,
                     win=float((arr > 0).mean()) * 100 if len(arr) else np.nan,
                     sharpe=sh, n=len(arr))

    L = ["# 2y PIT 行业轮动回测（市场中性化）\n",
         "> 脚本：`tools/research/sector_rotation_backtest_2y.py`",
         f"> 样本：**{len(d):,}** 行 / **{d['Scan_Date'].nunique()}** 个 Scan_Date / "
         f"**{d['Sector'].nunique()}** 个 Sector",
         f"> 行业动量代理：`{MOM}`（该表无 `Sector_RS_20D_Pct`）；每日取最强/最弱各 {TOP_N} 个 Sector",
         "> **收益口径：超额收益**（个股 − 当日全市场均值）⇒ **已剔除大盘 beta** ✓\n",
         "## 1. 超额收益对比（市场中性）\n",
         "| 组合 | 5D | 10D | 20D |", "|---|---|---|---|"]
    for name, df in (("**最强 3 行业**", S), ("**最弱 3 行业**", W)):
        cells = []
        for h in HORIZONS:
            x = st(df, h)
            cells.append(f"**{x['mean']:+.3f}%**（胜率 {x['win']:.1f}%, n={x['n']}）")
        L.append(f"| {name} | " + " | ".join(cells) + " |")
    L.append("")

    L += ["## 2. 多空（强 − 弱，按日计算）\n",
          "| 期限 | 多空超额 | 胜率 | 夏普* | 日数 |", "|---|---|---|---|---|"]
    for h in HORIZONS:
        m = ls[h]
        L.append(f"| {h}D | **{m['mean']:+.4f}%** | {m['win']:.1f}% | **{m['sharpe']:.2f}** | {m['n']} |")
    L.append("\n`*` 夏普含前瞻重叠偏差（5D/10D/20D 重叠 ⇒ 高估）；按日序列计算。\n")

    L += ["## 3. 结论\n"]
    m20 = ls[20]
    L.append(f"- **20D 多空超额 = {m20['mean']:+.4f}%**，夏普 **{m20['sharpe']:.2f}**，胜率 {m20['win']:.1f}%")
    s20, w20 = st(S, 20), st(W, 20)
    L.append(f"- 最强 3 行业 20D 超额 {s20['mean']:+.3f}%（n={s20['n']}）；"
             f"最弱 3 行业 {w20['mean']:+.3f}%（n={w20['n']}）")
    if m20["mean"] > 0:
        L.append("- ✅ **剔除市场涨跌后，买强行业仍有正超额** ⇒ 存在轮动 alpha ✓")
    else:
        L.append("- ✗ **剔除市场涨跌后，买强行业无正超额** ⇒ **不存在轮动 alpha**")
    L.append(f"- **成本覆盖判断**：双边成本约 0.1-0.3% ⇒ "
             f"{'**可覆盖**' if abs(m20['mean']) > 0.3 else '**无法覆盖**'}（20D 多空绝对值 {abs(m20['mean']):.4f}%）")
    L.append("")

    L += ["## 4. ⚠️ 限制\n",
          "1. **Sector 用当前 `sp500_constituents.csv` 映射** ⇒ PIT 行业漂移不可复现 ✗",
          "2. 行业动量用 `Momentum_20D_Pct`（**个股动量），非真正的行业指数动量** ✗",
          "3. **前瞻收益重叠** ⇒ 夏普高估约 √(252/h)；未做非重叠抽样 ✓",
          "4. 未扣交易成本、未做流动性/市值加权 ✓",
          "5. 超额基准是**等权全市场均值**（非 SPY 市值加权）✓",
          ""]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"written: {OUT} ({OUT.stat().st_size} bytes)")
    for h in HORIZONS:
        print(f"  L/S {h}D: {ls[h]['mean']:+.4f}% win={ls[h]['win']:.1f}% sharpe={ls[h]['sharpe']:.2f} n={ls[h]['n']}")
    print(f"  strong20={s20['mean']:+.3f}% weak20={w20['mean']:+.3f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
