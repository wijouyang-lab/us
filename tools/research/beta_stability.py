#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A 诊断：滚动 beta 稳定性 + 换手率

1. 每月末用过去 60 交易日拟合 OLS，观察各因子 beta 的时间序列
2. 计算换手率（相邻期信号分位变化）
3. 成本敏感性（5/10/20/50 bps）
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
RET_COL = "Forward_Return_20D"
FACTORS = [
    "ATR_Pct", "Momentum_60D_Pct", "Volume_Ratio_20D", "量比",
    "KDJ_J", "ZScore_20D", "Beta_60D_SPY", "Stock_RS_20D_vs_SPY",
]


def fit_ols(df, factors, y_col):
    sub = df[factors + [y_col]].copy()
    for c in factors + [y_col]:
        sub[c] = pd.to_numeric(sub[c], errors="coerce")
    sub = sub.dropna()
    if len(sub) < 100:
        return None
    X = np.column_stack([np.ones(len(sub)), sub[factors].values])
    y = sub[y_col].values
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    return beta


def main():
    bt = pd.read_csv("bt_pit.csv", encoding="utf-8-sig")
    bt["Scan_Date"] = pd.to_datetime(bt["Scan_Date"])
    dates = sorted(bt["Scan_Date"].unique())
    print(f"全样本: {len(bt)} 行, {len(dates)} 天")

    # === 1. 滚动 beta（每月末，用过去 60 交易日）===
    print("\n=== 滚动 beta 稳定性（每月末，60 日窗口）===")
    month_ends = []
    prev_month = None
    prev_date = None
    for d in dates:
        m = (d.year, d.month)
        if prev_month and m != prev_month:
            month_ends.append(prev_date)
        prev_month = m
        prev_date = d
    month_ends.append(prev_date)

    beta_history = {f: [] for f in FACTORS}
    for me in month_ends:
        idx = dates.index(me)
        if idx < 60:
            continue
        window_dates = dates[max(0, idx - 60):idx + 1]
        sub = bt[bt["Scan_Date"].isin(window_dates)]
        if len(sub) < 500:
            continue
        beta = fit_ols(sub, FACTORS, RET_COL)
        if beta is None:
            continue
        for i, f in enumerate(FACTORS):
            beta_history[f].append(beta[i + 1])

    print(f"滚动窗口数: {len(beta_history[FACTORS[0]])}")
    print(f"{'Factor':32s} | {'均值':>10s} | {'标准差':>10s} | {'符号翻转次数':>12s}")
    print("-" * 75)
    for f in FACTORS:
        arr = np.array(beta_history[f])
        if len(arr) == 0:
            continue
        mean_v = arr.mean()
        std_v = arr.std()
        signs = np.sign(arr)
        flips = np.sum(np.abs(np.diff(signs)) > 0) / 2
        print(f"{f:32s} | {mean_v:+.6f} | {std_v:.6f} | {int(flips):12d}")

    # === 2. 换手率 ===
    print("\n=== 换手率估算 ===")
    beta_full = fit_ols(bt, FACTORS, RET_COL)
    bt_sig = bt.copy()
    bt_sig["signal"] = beta_full[0]
    for i, f in enumerate(FACTORS):
        bt_sig[f] = pd.to_numeric(bt_sig[f], errors="coerce")
        z = bt_sig.groupby("Scan_Date")[f].transform(
            lambda s: (s - s.mean()) / s.std() if s.std() > 0 else 0
        )
        bt_sig["signal"] += beta_full[i + 1] * z

    bt_sig["quintile"] = bt_sig.groupby("Scan_Date")["signal"].transform(
        lambda s: pd.qcut(s, 5, labels=False, duplicates="drop")
    )

    sampled_dates = dates[::20]
    turnovers = []
    for i in range(1, len(sampled_dates)):
        d_prev = sampled_dates[i - 1]
        d_cur = sampled_dates[i]
        set_prev = set(bt_sig[(bt_sig["Scan_Date"] == d_prev) & (bt_sig["quintile"] == 4)]["Ticker"])
        set_cur = set(bt_sig[(bt_sig["Scan_Date"] == d_cur) & (bt_sig["quintile"] == 4)]["Ticker"])
        if len(set_prev) == 0 or len(set_cur) == 0:
            continue
        changed = len(set_cur - set_prev)
        turnover = changed / len(set_cur)
        turnovers.append(turnover)

    if turnovers:
        avg_turnover = np.mean(turnovers) * 100
        print(f"Q5 组平均换手率（每 20 日）: {avg_turnover:.1f}%")
        print(f"换手率样本数: {len(turnovers)}")
    else:
        avg_turnover = 100.0
        print("换手率无法计算，保守假设 100%")

    # === 3. 成本敏感性 ===
    print("\n=== 成本敏感性分析 ===")
    daily = bt_sig.groupby(["Scan_Date", "quintile"])[RET_COL].mean().reset_index()
    pivot = daily.pivot(index="Scan_Date", columns="quintile", values=RET_COL).dropna()
    ls = pivot[4] - pivot[0]
    ls_sampled = ls.loc[ls.index.isin(sampled_dates)]
    mean_ls = ls_sampled.mean() * 100
    t_stat = ls_sampled.mean() / (ls_sampled.std() / np.sqrt(len(ls_sampled))) if ls_sampled.std() > 0 else 0

    print(f"非重叠多空（每 20 日）: {mean_ls:+.4f}% | t={t_stat:+.3f} | n={len(ls_sampled)}")
    print()
    print(f"{'单边成本(bps)':>12s} | {'双边成本(%)':>12s} | {'净收益(%)':>10s} | {'净 t':>8s} | 判定")
    print("-" * 75)
    for bps in [5, 10, 20, 50]:
        cost_pct = bps / 10000 * 2 * (avg_turnover / 100) * 100
        net_ret = mean_ls - cost_pct
        net_t = (net_ret - 0) / (ls_sampled.std() * 100) * np.sqrt(len(ls_sampled)) if ls_sampled.std() > 0 else 0
        verdict = "✓ 可交易" if net_t > 2 else "⚠ 边界" if net_t > 1 else "✗ 不可交易"
        print(f"{bps:>12d} | {cost_pct:>12.4f} | {net_ret:>+10.4f} | {net_t:>+8.3f} | {verdict}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
