#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A 线：去共线化后的多因子等权打分 + 分层（Q1-Q5）回测。

只读研究脚本：
  输入  research_factor_snapshots_sp500_pit_2y.csv（22 列 PIT 快照）
        research_backtest_sp500_pit_2y.csv（含 Forward_Return_{5,10,20}D）
  输出  docs/FACTOR_QUANTILE_BACKTEST.md

剔除（依据 factor_orthogonality_diag.py 实测）：
  · Realized_Volatility_20D_Pct  —— 与 ATR_Pct ρ=+0.884（同一风险维度）
  · MA20 / MA50                  —— 互相 VIF≈589，且 OLS t≈0.25（无独立解释力）

打分方向（SIGN）说明：取本会话 IC 实测符号（PIT 2Y @20D）：
  正：ATR_Pct(+0.0726)、Beta_60D_SPY(+0.0621)、Volume_Ratio_20D(+0.0057)
  负：Momentum_*、RSI、MA20_Slope、乖离率、ZScore、Stock_RS、KDJ_J、MACD_HIST、量比
  ⇒ 「因子值越高 → 预期收益越低」的取 -1（等价于把排名反转为低值优先）。
  ⚠️ 该方向来自**同一样本内的 IC**（in-sample），属已知乐观偏差，报告内明示。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
SNAP = REPO / "research_factor_snapshots_sp500_pit_2y.csv"
BT = REPO / "research_backtest_sp500_pit_2y.csv"
OUT = REPO / "docs" / "FACTOR_QUANTILE_BACKTEST.md"

SIGN = {
    "ATR_Pct": +1, "Beta_60D_SPY": +1, "Volume_Ratio_20D": +1,
    "Momentum_5D_Pct": -1, "Momentum_20D_Pct": -1, "Momentum_60D_Pct": -1,
    "RSI": -1, "MA20_Slope_Pct_5D": -1, "乖离率(%)": -1, "ZScore_20D": -1,
    "Stock_RS_20D_vs_SPY": -1, "KDJ_J": -1, "MACD_HIST_LAST": -1, "量比": -1,
}
DROPPED = ["Realized_Volatility_20D_Pct", "MA20", "MA50"]
HORIZONS = (5, 10, 20)
Q = 5


def main() -> int:
    if not SNAP.exists() or not BT.exists():
        raise SystemExit("missing inputs")
    print(f"loading {SNAP.name} …")
    snap = pd.read_csv(SNAP, dtype=str, keep_default_na=False)
    bt = pd.read_csv(BT, dtype=str, keep_default_na=False,
                     usecols=["Ticker", "Technical_Date"] +
                     [f"Forward_Return_{h}D" for h in HORIZONS])
    key = ["Ticker", "Technical_Date"]
    df = snap.merge(bt, on=key, how="inner")
    print(f"  merged rows={len(df)}")

    factors = [f for f in SIGN if f in df.columns]
    num_cols = factors + [f"Forward_Return_{h}D" for h in HORIZONS]
    d = df[key + num_cols].copy()
    for c in num_cols:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=[f"Forward_Return_20D"])
    d["Technical_Date"] = pd.to_datetime(d["Technical_Date"], errors="coerce")
    d = d.dropna(subset=["Technical_Date"])
    print(f"  usable rows={len(d)}  factors={len(factors)}  dates={d['Technical_Date'].nunique()}")

    # ---------- 横截面百分位（按日）----------
    g = d.groupby("Technical_Date")
    ranked = pd.DataFrame(index=d.index)
    for f in factors:
        pct = g[f].rank(pct=True)          # 0~1
        ranked[f] = pct * SIGN[f]
    d["Composite"] = ranked[factors].mean(axis=1)   # 等权（含方向）
    d = d.dropna(subset=["Composite"])

    # ---------- 分位 ----------
    d["Q"] = g["Composite"].transform(
        lambda s: pd.qcut(s.rank(method="first"), Q, labels=False) + 1
        if len(s) >= Q else np.nan)
    d = d.dropna(subset=["Q"])

    # ---------- 分层收益 ----------
    rows = {}
    daily_q = {}
    for h in HORIZONS:
        ret = f"Forward_Return_{h}D"
        per = d.groupby(["Technical_Date", "Q"])[ret].mean().unstack()
        daily_q[h] = per
        rows[h] = {int(q): float(per[q].mean()) * 100 for q in per.columns}

    # 多空（Q5 - Q1）+ 夏普（按 20 日非重叠视角给参考）
    ls_stats = {}
    for h in HORIZONS:
        per = daily_q[h].dropna()
        ls = per[Q] - per[1]
        sharpe = (ls.mean() / ls.std() * np.sqrt(252 / h)) if ls.std() > 0 else float("nan")
        ann = ls.mean() * (252 / h)
        ls_stats[h] = dict(mean=ls.mean() * 100, sharpe=sharpe, annual=ann * 100,
                           win=(ls > 0).mean() * 100, n=len(ls))

    # 胜率（分组为正收益的比例）
    win_rate = {}
    for h in HORIZONS:
        ret = f"Forward_Return_{h}D"
        win_rate[h] = {int(q): float((d[d["Q"] == q][ret] > 0).mean() * 100)
                       for q in sorted(d["Q"].unique())}

    # ---------- 报告 ----------
    L = []
    L.append("# 多因子分层回测报告（S&P500 PIT 2Y，去共线后 14 因子）\n")
    L.append("> 生成脚本：`tools/research/factor_quantile_backtest.py`")
    L.append(f"> 样本：**{len(d):,}** 行 / **{d['Technical_Date'].nunique()}** 个交易日 / **{len(factors)}** 个因子")
    L.append("> 剔除（正交性诊断实测）：" + "、".join(f"`{x}`" for x in DROPPED) + "\n")

    L.append("## 1. 打分方法\n")
    L.append("- 每日（`Technical_Date`）**横截面百分位**（0~1）+ **方向化**（见下）")
    L.append("- **等权**相加 → `Composite`，再按日分 5 层（Q1 最低 → **Q5 最高分**）")
    L.append("- 方向（SIGN，来自 PIT 2Y 的 IC 符号，**in-sample**）：")
    L.append("  - `+1`：" + "、".join(f"`{k}`" for k, v in SIGN.items() if v > 0))
    L.append("  - `-1`（越高越优先做空/回避）：" +
             "、".join(f"`{k}`" for k, v in SIGN.items() if v < 0))
    L.append("")

    L.append("## 2. 分层平均收益（%）\n")
    L.append("| 层 | 5D | 10D | 20D | 5D 胜率 | 10D 胜率 | 20D 胜率 |")
    L.append("|---|---|---|---|---|---|---|")
    for q in range(1, Q + 1):
        L.append("| Q{}{} | {:.4f} | {:.4f} | {:.4f} | {:.1f}% | {:.1f}% | {:.1f}% |".format(
            q, "（最低分）" if q == 1 else ("（最高分）" if q == Q else ""),
            rows[5].get(q, float("nan")), rows[10].get(q, float("nan")),
            rows[20].get(q, float("nan")),
            win_rate[5].get(q, float("nan")), win_rate[10].get(q, float("nan")),
            win_rate[20].get(q, float("nan"))))
    L.append("")

    L.append("## 3. 多空组合（Q5 − Q1）\n")
    L.append("| 持有期 | 多空均值(%) | 年化夏普 | 年化收益(%) | 胜率 | 交易日数 |")
    L.append("|---|---|---|---|---|---|")
    for h in HORIZONS:
        s = ls_stats[h]
        L.append(f"| {h}D | **{s['mean']:+.4f}** | **{s['sharpe']:.2f}** | {s['annual']:+.2f} | "
                 f"{s['win']:.1f}% | {s['n']} |")
    L.append("")

    L.append("## 4. 核心结论\n")
    s20 = ls_stats[20]
    mono = all(rows[20].get(i, 0) <= rows[20].get(i + 1, 0) for i in range(1, Q))
    L.append(f"- **Q5（最高分）vs Q1（最低分）@20D**：{rows[20].get(Q, float('nan')):+.4f}% "
             f"vs {rows[20].get(1, float('nan')):+.4f}% → **差 {s20['mean']:+.4f}%**")
    L.append(f"- **多空夏普**：5D **{ls_stats[5]['sharpe']:.2f}** / 10D "
             f"**{ls_stats[10]['sharpe']:.2f}** / 20D **{s20['sharpe']:.2f}**")
    L.append(f"- **20D 分层单调性**：{'✅ 单调递增（Q1→Q5）' if mono else '✗ 非单调'}")
    L.append(f"- **是否 Q5 优于 Q1**：{'✅ 是' if s20['mean'] > 0 else '✗ 否'}"
             f"（20D 差 {s20['mean']:+.4f}%）")
    L.append("")
    L.append("### ⚠️ 必读偏差提示\n")
    L.append("1. **方向来自 in-sample IC** ⇒ 存在前视乐观（真实 OOS 会更差）。")
    L.append("2. **Forward_Return 重叠**（每日都有 20 日前瞻）⇒ 夏普被高估约 √20（见 P0 加固经验）。")
    L.append("3. **未扣交易成本**；分层组合换手高，成本可能吞掉全部价差。")
    L.append("4. 本报告只说明**因子打分的横截面区分度**，不等于可交易策略。")
    L.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"\nwritten: {OUT} ({OUT.stat().st_size} bytes)")

    print("\n=== 分层 20D ===")
    for q in range(1, Q + 1):
        print(f"  Q{q}: {rows[20].get(q, float('nan')):+.4f}%  (win {win_rate[20].get(q, float('nan')):.1f}%)")
    print("=== 多空 ===")
    for h in HORIZONS:
        s = ls_stats[h]
        print(f"  {h}D: {s['mean']:+.4f}%  sharpe={s['sharpe']:.2f}  win={s['win']:.1f}%  n={s['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
