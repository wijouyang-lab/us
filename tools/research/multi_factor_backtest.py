#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多因子组合回测（S&P500 PIT 池）

用 A 的 OLS 系数构造组合信号，做分位回测 + 交易成本分析。
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent

# A 的 OLS 结果（|t| > 3 的因子）
OLS_BETA = {
    "ATR_Pct": +0.011809,
    "Momentum_60D_Pct": -0.000183,
    "Volume_Ratio_20D": -0.007818,
    "量比": +0.008237,
    "KDJ_J": +0.000078,
    "ZScore_20D": -0.002288,
    "Beta_60D_SPY": +0.001194,
    "Stock_RS_20D_vs_SPY": +0.000190,
}
RET_COL = "Forward_Return_20D"
COST_BPS = 10  # 单边交易成本 10 bps


def build_signal(df):
    """用 OLS 系数构造组合信号"""
    df = df.copy()
    factors = list(OLS_BETA.keys())
    for f in factors:
        df[f] = pd.to_numeric(df[f], errors="coerce")
    df["signal"] = 0.0
    for f, beta in OLS_BETA.items():
        z = df.groupby("Scan_Date")[f].transform(
            lambda s: (s - s.mean()) / s.std() if s.std() > 0 else 0
        )
        df["signal"] += beta * z
    return df


def backtest_quintile(df, label):
    """分位回测"""
    df = df.copy()
    df["quintile"] = df.groupby("Scan_Date")["signal"].transform(
        lambda s: pd.qcut(s, 5, labels=False, duplicates="drop")
    )
    daily = df.groupby(["Scan_Date", "quintile"])[RET_COL].mean().reset_index()
    pivot = daily.pivot(index="Scan_Date", columns="quintile", values=RET_COL).dropna()
    if pivot.empty:
        print(f"[{label}] 无法分组")
        return None

    avg = pivot.mean() * 100
    print(f"\n[{label}] 分位平均 20D 收益（%）:")
    for q in avg.index:
        print(f"  Q{int(q)+1}: {avg[q]:+.4f}%")

    if 0 in pivot.columns and 4 in pivot.columns:
        ls = pivot[4] - pivot[0]  # 多头 Q5 - 空头 Q1（信号高做多）
        mean_ls = ls.mean() * 100
        t_stat = ls.mean() / (ls.std() / np.sqrt(len(ls))) if ls.std() > 0 else 0
        print(f"\n[{label}] 多空（Q5 高信号 - Q1 低信号）:")
        print(f"  平均 20D 收益: {mean_ls:+.4f}%")
        print(f"  t 统计量: {t_stat:+.3f}")
        print(f"  样本天数: {len(ls)}")

        turnover_cost = COST_BPS / 10000 * 2  # 单边 10bps x 2（开+平）
        cost_pct = turnover_cost * 100
        net_ret = mean_ls - cost_pct
        print(f"  双边交易成本（{COST_BPS}bps x 2）: {cost_pct:.4f}%")
        print(f"  净收益（扣成本）: {net_ret:+.4f}%")
        if ls.std() > 0:
            print(f"  净 t 统计量: {(net_ret - 0)/(ls.std()/np.sqrt(len(ls))*100):+.3f}")

        if ls.std() > 0:
            sharpe = mean_ls / (ls.std() * 100) * np.sqrt(252/20)
            print(f"  年化夏普（粗略）: {sharpe:.2f}")
            sharpe_net = net_ret / (ls.std() * 100) * np.sqrt(252/20)
            print(f"  净年化夏普: {sharpe_net:.2f}")
    return pivot


def main():
    bt = pd.read_csv("bt_pit.csv", encoding="utf-8-sig")
    print(f"样本量: {len(bt)}")

    bt = build_signal(bt)
    bt = bt.dropna(subset=["signal", RET_COL])

    backtest_quintile(bt, "全样本")

    dates = sorted(bt["Scan_Date"].unique())
    split_idx = int(len(dates) * 0.7)
    train_dates = set(dates[:split_idx])
    test_dates = set(dates[split_idx:])

    bt_train = bt[bt["Scan_Date"].isin(train_dates)]
    bt_test = bt[bt["Scan_Date"].isin(test_dates)]

    backtest_quintile(bt_train, "样本内（前 70%）")
    backtest_quintile(bt_test, "样本外（后 30%）")

    return 0


if __name__ == "__main__":
    sys.exit(main())
