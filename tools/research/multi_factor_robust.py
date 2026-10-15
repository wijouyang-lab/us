#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多因子组合统计可信度加固

P0-1：纯样本外 β（只用前 70% 拟合 OLS 系数，后 30% 测试）
P0-2：非重叠 20 日窗检验（每 20 天取一个观测，消除重叠自相关）
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

REPO = Path(__file__).resolve().parent.parent.parent
RET_COL = "Forward_Return_20D"
FACTORS = [
    "ATR_Pct", "Momentum_60D_Pct", "Volume_Ratio_20D", "量比",
    "KDJ_J", "ZScore_20D", "Beta_60D_SPY", "Stock_RS_20D_vs_SPY",
]


def fit_ols(df, factors, y_col):
    """在 df 上拟合 OLS，返回系数（含截距）"""
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


def signal_from_beta(df, factors, beta):
    """用给定 β 构造信号（标准化后加权）"""
    df = df.copy()
    df["signal"] = beta[0]
    for i, f in enumerate(factors):
        df[f] = pd.to_numeric(df[f], errors="coerce")
        z = df.groupby("Scan_Date")[f].transform(
            lambda s: (s - s.mean()) / s.std() if s.std() > 0 else 0
        )
        df["signal"] += beta[i + 1] * z
    return df


def backtest_ls(df, label, ret_col=RET_COL):
    """多空回测：按 signal 分 5 组，Q5 - Q1"""
    df = df.copy()
    df["quintile"] = df.groupby("Scan_Date")["signal"].transform(
        lambda s: pd.qcut(s, 5, labels=False, duplicates="drop")
    )
    daily = df.groupby(["Scan_Date", "quintile"])[ret_col].mean().reset_index()
    pivot = daily.pivot(index="Scan_Date", columns="quintile", values=ret_col).dropna()
    if pivot.empty or 0 not in pivot.columns or 4 not in pivot.columns:
        print(f"[{label}] 无法分组")
        return None
    ls = pivot[4] - pivot[0]
    mean_ls = ls.mean() * 100
    t_stat = ls.mean() / (ls.std() / np.sqrt(len(ls))) if ls.std() > 0 else 0
    print(f"[{label}] 多空: {mean_ls:+.4f}% | t={t_stat:+.3f} | n={len(ls)}")
    return ls


def main():
    bt = pd.read_csv("bt_pit.csv", encoding="utf-8-sig")
    bt["Scan_Date"] = pd.to_datetime(bt["Scan_Date"])
    print(f"全样本: {len(bt)} 行, {bt['Scan_Date'].nunique()} 天")

    dates = sorted(bt["Scan_Date"].unique())
    split_idx = int(len(dates) * 0.7)
    train_dates = set(dates[:split_idx])
    test_dates = set(dates[split_idx:])
    print(f"样本内: {len(train_dates)} 天, 样本外: {len(test_dates)} 天")

    # P0-1：纯样本外 β
    print("\n=== P0-1：纯样本外 beta（用 IS 拟合，OOS 测试）===")
    bt_train = bt[bt["Scan_Date"].isin(train_dates)]
    bt_test = bt[bt["Scan_Date"].isin(test_dates)]
    beta_is = fit_ols(bt_train, FACTORS, RET_COL)
    if beta_is is None:
        print("IS 拟合失败")
        return 1
    print("IS 系数:")
    for i, f in enumerate(FACTORS):
        print(f"  {f:32s}: {beta_is[i+1]:+.6f}")

    bt_test_sig = signal_from_beta(bt_test, FACTORS, beta_is)
    backtest_ls(bt_test_sig, "纯样本外（IS beta -> OOS 测试）")

    # P0-2：非重叠 20 日窗
    print("\n=== P0-2：非重叠 20 日窗（每 20 天取一个观测）===")
    beta_full = fit_ols(bt, FACTORS, RET_COL)
    bt_sig = signal_from_beta(bt, FACTORS, beta_full)

    unique_dates = sorted(bt_sig["Scan_Date"].unique())
    sampled_dates = unique_dates[::20]
    print(f"采样日期数: {len(sampled_dates)}")
    bt_nov = bt_sig[bt_sig["Scan_Date"].isin(sampled_dates)]
    backtest_ls(bt_nov, "非重叠 20 日窗（全样本 beta）")

    bt_nov_is = bt_nov[bt_nov["Scan_Date"].isin(train_dates)]
    bt_nov_oos = bt_nov[bt_nov["Scan_Date"].isin(test_dates)]
    backtest_ls(bt_nov_is, "非重叠 20 日窗（IS）")
    backtest_ls(bt_nov_oos, "非重叠 20 日窗（OOS）")

    return 0


if __name__ == "__main__":
    sys.exit(main())
