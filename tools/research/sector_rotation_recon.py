#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""行业轮动因子侦察（只读）：最强/最弱 Sector 的横截面前瞻收益对比。

数据：quant_factor_snapshot.csv（Sector / Scan_Date / Sector_RS_20D_Pct）
      quant_factor_backtest.csv（Forward_Return_5D/10D/20D）
输出：docs/SECTOR_ROTATION_RECON.md

⚠️ 数据边界（实测）：Forward_Return_5D 非空 1342 行；10D 仅 5 行；20D 全空
   ⇒ 统计以 5D 为主，10D 仅供参考，20D 不可用（如实标注）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
SNAP = REPO / "quant_factor_snapshot.csv"
BT = REPO / "quant_factor_backtest.csv"
OUT = REPO / "docs" / "SECTOR_ROTATION_RECON.md"

TOP_N = 3
HORIZONS = (5, 10)


def main() -> int:
    if not SNAP.exists() or not BT.exists():
        raise SystemExit("missing inputs")
    snap = pd.read_csv(SNAP, dtype=str, keep_default_na=False)
    bt = pd.read_csv(BT, dtype=str, keep_default_na=False)

    key = ["Ticker", "Technical_Date"]
    cols = key + ["Scan_Date"] + [f"Forward_Return_{h}D" for h in HORIZONS]
    cols = [c for c in cols if c in bt.columns]
    d = snap.merge(bt[cols], on=key, how="inner", suffixes=("", "_bt"))
    if "Scan_Date_bt" in d.columns:
        d["Scan_Date"] = d["Scan_Date_bt"]

    for c in ["Sector_RS_20D_Pct"] + [f"Forward_Return_{h}D" for h in HORIZONS]:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=["Sector_RS_20D_Pct", "Forward_Return_5D"])
    d["Sector"] = d["Sector"].fillna("NA").replace("", "NA")
    print(f"usable rows={len(d)} dates={d['Scan_Date'].nunique()} "
          f"sectors={d['Sector'].nunique()}")

    # ---------- 每日 Sector 强度排名 ----------
    rows_strong, rows_weak = [], []
    daily_rank = []
    for dt, day in d.groupby("Scan_Date"):
        g = day.groupby("Sector")["Sector_RS_20D_Pct"].mean().sort_values(ascending=False)
        if len(g) < TOP_N * 2:
            continue
        strong = list(g.index[:TOP_N])
        weak = list(g.index[-TOP_N:])
        daily_rank.append((dt, strong, weak, len(day)))
        rows_strong.append(day[day["Sector"].isin(strong)])
        rows_weak.append(day[day["Sector"].isin(weak)])

    if not daily_rank:
        raise SystemExit("no dates with enough sectors")

    S = pd.concat(rows_strong) if rows_strong else pd.DataFrame()
    W = pd.concat(rows_weak) if rows_weak else pd.DataFrame()

    def stat(df, h):
        v = pd.to_numeric(df[f"Forward_Return_{h}D"], errors="coerce").dropna()
        if not len(v):
            return dict(mean=np.nan, win=np.nan, n=0)
        return dict(mean=float(v.mean()) * 100, win=float((v > 0).mean()) * 100, n=int(len(v)))

    L = ["# 行业轮动因子侦察（最强 vs 最弱 Sector）\n",
         "> 脚本：`tools/research/sector_rotation_recon.py`",
         f"> 样本：**{len(d)}** 行 / **{d['Scan_Date'].nunique()}** 个 Scan_Date / "
         f"**{d['Sector'].nunique()}** 个 Sector",
         f"> 排序依据：每日按 `Sector_RS_20D_Pct` 的 Sector 内均值排序，取前 {TOP_N} 强 / 后 {TOP_N} 弱",
         "> ⚠️ **数据边界**：`Forward_Return_5D` 非空 1342 行；**10D 仅 5 行、20D 全空** ⇒ "
         "**5D 是唯一可结论的期限** ✓\n",
         "## 1. 最强 vs 最弱 Sector（个股等权）\n",
         "| 组合 | 期限 | 平均收益 | 胜率 | 样本数 |", "|---|---|---|---|---|"]
    res = {}
    for name, df in (("**最强 3 Sector**", S), ("**最弱 3 Sector**", W), ("全市场基准", d)):
        for h in HORIZONS:
            st = stat(df, h)
            res[(name, h)] = st
            L.append(f"| {name} | {h}D | **{st['mean']:+.3f}%** | {st['win']:.1f}% | {st['n']} |")
    L.append("")

    s5 = stat(S, 5)
    w5 = stat(W, 5)
    m5 = stat(d, 5)
    spread = s5["mean"] - w5["mean"]
    L += ["## 2. 核心对比（5D）\n",
          f"- **最强 3 Sector**：{s5['mean']:+.3f}%（胜率 {s5['win']:.1f}%，n={s5['n']}）",
          f"- **最弱 3 Sector**：{w5['mean']:+.3f}%（胜率 {w5['win']:.1f}%，n={w5['n']}）",
          f"- **多空差（强 − 弱）**：**{spread:+.3f} pp**" + (" ✅ 方向正确" if spread > 0 else " ✗ 方向相反"),
          f"- **全市场基准**：{m5['mean']:+.3f}%（胜率 {m5['win']:.1f}%，n={m5['n']}）",
          f"- **强势超额（强 − 全市场）**：**{s5['mean'] - m5['mean']:+.3f} pp**",
          ""]

    L += ["## 3. 每日强弱 Sector 明细\n",
          "| Scan_Date | 最强 3 | 最弱 3 | 当日股票数 |", "|---|---|---|---|"]
    for dt, strong, weak, n in daily_rank:
        L.append(f"| {dt} | {', '.join(strong)} | {', '.join(weak)} | {n} |")
    L.append("")

    L += ["## 4. ⚠️ 限制（必读）\n",
          "1. **仅 5D 可结论** ✗ —— 10D 只有 5 行、20D 为 0（价格历史未覆盖足够前瞻）✓",
          "2. **仅 9 个 Scan_Date** ⇒ 重叠偏差严重，**统计量不可当稳健结论** ✓",
          "3. `Sector_RS_20D_Pct` 本身是**过去 20 日**的相对强度 ⇒ 该检验是「**动量延续**」检验 ✓",
          "4. 未扣成本；未做行业市值加权（**个股等权** ✓）",
          "5. 未区分 `market_regime`（牛/熊市中轮动效应可能反转）✓",
          ""]

    L += ["## 5. 判读\n"]
    if spread > 0:
        L.append(f"- **方向支持行业轮动**（强 − 弱 = {spread:+.3f} pp）✓，但**幅度需与成本对比** ✓")
    else:
        L.append(f"- **方向不支持行业轮动**（强 − 弱 = {spread:+.3f} pp）✗")
    L.append(f"- **强势超额** {s5['mean'] - m5['mean']:+.3f} pp ⇒ "
             + ("**选强行业有用** ✓" if s5["mean"] > m5["mean"] else "**选强行业无用** ✗"))
    L.append("- **任一 |差| < 0.5 pp 时，在 n<1000、9 个日期的条件下基本是噪声** ✗")
    L.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"written: {OUT} ({OUT.stat().st_size} bytes)")
    print(f"  strong5={s5['mean']:+.3f}% weak5={w5['mean']:+.3f}% spread={spread:+.3f}pp "
          f"market5={m5['mean']:+.3f}% excess={s5['mean']-m5['mean']:+.3f}pp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
