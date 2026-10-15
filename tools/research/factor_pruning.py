#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""组合精简验证

对比四套因子集的非重叠多空表现：
A. 全 8 因子（基准）
B. 剔除 KDJ_J + Beta_60D_SPY
C. 仅 ATR_Pct（单因子组合）
D. 仅稳定 3 因子（ATR_Pct + 量比 + Stock_RS）
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
RET_COL = "Forward_Return_20D"
COST_BPS = 20

FACTOR_SETS = {
    "A_全8因子": [
        "ATR_Pct", "Momentum_60D_Pct", "Volume_Ratio_20D", "量比",
        "KDJ_J", "ZScore_20D", "Beta_60D_SPY", "Stock_RS_20D_vs_SPY",
    ],
    "B_剔除不稳定": [
        "ATR_Pct", "Momentum_60D_Pct", "Volume_Ratio_20D", "量比",
        "ZScore_20D", "Stock_RS_20D_vs_SPY",
    ],
    "C_仅ATR": ["ATR_Pct"],
    "D_仅稳定3因子": ["ATR_Pct", "量比", "Stock_RS_20D_vs_SPY"],
}


def fit_ols(df, factors, y_col):
    sub = df[factors + [y_col]].copy()
    for c in factors + [y_col]:
        sub[c] = pd.to_numeric(sub[c], errors="coerce")
    sub = sub.dropna()
    if len(sub) < 100:
        return None
    X = np.column_stack([np.ones(len(sub)), sub[factors].values])
    y = sub[y_col].values
    return np.linalg.lstsq(X, y, rcond=None)[0]


def signal_from_beta(df, factors, beta):
    df = df.copy()
    df["signal"] = beta[0]
    for i, f in enumerate(factors):
        df[f] = pd.to_numeric(df[f], errors="coerce")
        z = df.groupby("Scan_Date")[f].transform(
            lambda s: (s - s.mean()) / s.std() if s.std() > 0 else 0
        )
        df["signal"] += beta[i + 1] * z
    return df


def backtest_nonoverlap(df, label, sampled_dates):
    df = df.copy()
    df["quintile"] = df.groupby("Scan_Date")["signal"].transform(
        lambda s: pd.qcut(s, 5, labels=False, duplicates="drop")
    )
    daily = df.groupby(["Scan_Date", "quintile"])[RET_COL].mean().reset_index()
    pivot = daily.pivot(index="Scan_Date", columns="quintile", values=RET_COL).dropna()
    if pivot.empty or 0 not in pivot.columns or 4 not in pivot.columns:
        print(f"[{label}] 无法分组")
        return None
    ls = pivot[4] - pivot[0]
    ls_sampled = ls.loc[ls.index.isin(sampled_dates)]
    if len(ls_sampled) < 3:
        print(f"[{label}] 样本不足")
        return None
    mean_ls = ls_sampled.mean() * 100
    t_stat = ls_sampled.mean() / (ls_sampled.std() / np.sqrt(len(ls_sampled))) if ls_sampled.std() > 0 else 0
    cost_pct = COST_BPS / 10000 * 2 * 0.336 * 100
    net_ret = mean_ls - cost_pct
    net_t = (net_ret - 0) / (ls_sampled.std() * 100) * np.sqrt(len(ls_sampled)) if ls_sampled.std() > 0 else 0
    return {
        "label": label,
        "mean_ls": mean_ls,
        "t": t_stat,
        "net_ls": net_ret,
        "net_t": net_t,
        "n": len(ls_sampled),
    }


def main():
    bt = pd.read_csv("bt_pit.csv", encoding="utf-8-sig")
    bt["Scan_Date"] = pd.to_datetime(bt["Scan_Date"])
    dates = sorted(bt["Scan_Date"].unique())
    sampled_dates = dates[::20]
    print(f"全样本: {len(bt)} 行, {len(dates)} 天")
    print(f"非重叠采样: {len(sampled_dates)} 天\n")

    results = []
    for name, factors in FACTOR_SETS.items():
        print(f"=== {name} ===")
        beta = fit_ols(bt, factors, RET_COL)
        if beta is None:
            print("拟合失败\n")
            continue
        bt_sig = signal_from_beta(bt, factors, beta)
        res = backtest_nonoverlap(bt_sig, name, sampled_dates)
        if res:
            results.append(res)
            print(f"  多空: {res['mean_ls']:+.4f}% | t={res['t']:+.3f} | n={res['n']}")
            print(f"  扣 {COST_BPS}bps: {res['net_ls']:+.4f}% | 净 t={res['net_t']:+.3f}\n")

    print("=" * 90)
    print(f"{'Factor Set':32s} | {'多空':>10s} | {'t':>7s} | {'净多空':>10s} | {'净t':>7s} | n")
    print("=" * 90)
    for r in results:
        print(f"{r['label']:32s} | {r['mean_ls']:+9.4f}% | {r['t']:+7.3f} | {r['net_ls']:+9.4f}% | {r['net_t']:+7.3f} | {r['n']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
