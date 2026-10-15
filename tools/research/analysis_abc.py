#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A/B/C 三项因子深度分析

A. Beta_60D_SPY 独立增量价值（多因子 OLS）
B. 分层建模——266 池 vs S&P500 PIT 池因子对比
C. Momentum_60D 反向信号分位回测
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent


# ---------- 工具函数 ----------
def ols_with_tvalues(X, y):
    """手动 OLS 回归，返回系数、t 值、p 值（双尾）"""
    X = np.column_stack([np.ones(len(X)), X])  # 加截距
    try:
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        resid = y - X @ beta
        n, k = X.shape
        sigma2 = (resid @ resid) / (n - k)
        cov = sigma2 * np.linalg.inv(X.T @ X)
        se = np.sqrt(np.diag(cov))
        t = beta / se
        from scipy import stats
        p = 2 * (1 - stats.t.cdf(np.abs(t), df=n - k))
        return beta, t, p
    except Exception as e:
        print(f"OLS failed: {e}")
        return None, None, None


# ---------- A. Beta_60D_SPY 独立增量价值 ----------
def task_a(bt_pit):
    print("=" * 80)
    print("A. Beta_60D_SPY 独立增量价值（多因子 OLS，因变量 Forward_Return_20D）")
    print("=" * 80)
    factors = [
        "Momentum_5D_Pct", "Momentum_20D_Pct", "Momentum_60D_Pct",
        "Realized_Volatility_20D_Pct", "Volume_Ratio_20D", "ZScore_20D",
        "Beta_60D_SPY", "Stock_RS_20D_vs_SPY",
        "RSI", "MA20", "MA50", "MA20_Slope_Pct_5D", "ATR_Pct",
        "乖离率(%)", "MACD_HIST_LAST", "KDJ_J", "量比"
    ]
    y_col = "Forward_Return_20D"
    if y_col not in bt_pit.columns:
        print(f"缺少 {y_col}")
        return
    sub = bt_pit[factors + [y_col]].copy()
    for c in factors + [y_col]:
        sub[c] = pd.to_numeric(sub[c], errors="coerce")
    sub = sub.dropna()
    if len(sub) < 100:
        print("样本不足")
        return
    y = sub[y_col].values
    X = sub[factors].values
    beta, t, p = ols_with_tvalues(X, y)
    if beta is None:
        return
    print(f"样本量: {len(sub)}")
    print(f"{'Factor':32s} | {'Beta':>10s} | {'t':>8s} | {'p':>8s}")
    print("-" * 70)
    for i, f in enumerate(factors):
        print(f"{f:32s} | {beta[i+1]:+10.6f} | {t[i+1]:+8.3f} | {p[i+1]:8.5f}")
    print()
    idx = factors.index("Beta_60D_SPY")
    print(f"★ Beta_60D_SPY 系数={beta[idx+1]:+.6f}, t={t[idx+1]:+.3f}, p={p[idx+1]:.5f}")


# ---------- B. 分层建模对比 ----------
def task_b():
    print("=" * 80)
    print("B. 分层建模——266 池 vs S&P500 PIT 池因子 IC 对比")
    print("=" * 80)
    ic_266 = pd.read_csv("ic_266.csv", encoding="utf-8-sig")
    ic_pit = pd.read_csv("ic_pit.csv", encoding="utf-8-sig")
    ic_266 = ic_266[ic_266["Horizon"] == "20D"][["Factor", "IC_Spearman"]].rename(
        columns={"IC_Spearman": "IC_266"})
    ic_pit = ic_pit[ic_pit["Horizon"] == "20D"][["Factor", "IC_Spearman"]].rename(
        columns={"IC_Spearman": "IC_PIT"})
    merged = ic_266.merge(ic_pit, on="Factor", how="outer")
    merged["IC_diff"] = merged["IC_PIT"] - merged["IC_266"]
    merged = merged.sort_values("IC_diff", key=lambda x: x.abs(), ascending=False)
    print(f"{'Factor':32s} | {'IC_266':>10s} | {'IC_PIT':>10s} | {'Diff':>10s}")
    print("-" * 75)
    for _, row in merged.iterrows():
        print(f"{row['Factor']:32s} | {row['IC_266']:+10.4f} | {row['IC_PIT']:+10.4f} | {row['IC_diff']:+10.4f}")


# ---------- C. Momentum_60D 反向信号分位回测 ----------
def task_c(bt_pit):
    print("=" * 80)
    print("C. Momentum_60D 反向信号分位回测（S&P500 PIT 池）")
    print("=" * 80)
    col = "Momentum_60D_Pct"
    ret = "Forward_Return_20D"
    if col not in bt_pit.columns or ret not in bt_pit.columns:
        print("缺少列")
        return
    sub = bt_pit[["Scan_Date", col, ret]].copy()
    sub[col] = pd.to_numeric(sub[col], errors="coerce")
    sub[ret] = pd.to_numeric(sub[ret], errors="coerce")
    sub = sub.dropna()
    if len(sub) < 1000:
        print("样本不足")
        return

    def group_ret(g):
        g = g.copy()
        g["quintile"] = pd.qcut(g[col], 5, labels=False, duplicates="drop")
        return g.groupby("quintile")[ret].mean()

    sub["quintile"] = sub.groupby("Scan_Date")[col].transform(
        lambda s: pd.qcut(s, 5, labels=False, duplicates="drop"))
    daily = sub.groupby(["Scan_Date", "quintile"])[ret].mean().reset_index()
    daily.columns = ["Scan_Date", "quintile", "mean_ret"]
    pivot = daily.pivot(index="Scan_Date", columns="quintile", values="mean_ret").dropna()
    if pivot.empty:
        print("无法分组")
        return
    avg = pivot.mean() * 100
    print("分位平均 20D 收益（%）:")
    for q in avg.index:
        print(f"  Q{q+1}: {avg[q]:+.4f}%")
    if 0 in pivot.columns and 4 in pivot.columns:
        ls = pivot[0] - pivot[4]
        mean_ls = ls.mean() * 100
        t_stat = ls.mean() / (ls.std() / np.sqrt(len(ls))) if ls.std() > 0 else 0
        print("\n多空（Q1 最低 Momentum - Q5 最高 Momentum）:")
        print(f"  平均 20D 收益: {mean_ls:+.4f}%")
        print(f"  t 统计量: {t_stat:+.3f}")
        print(f"  样本天数: {len(ls)}")
        if t_stat != 0:
            print(f"  年化夏普（粗略）: {t_stat * np.sqrt(252/20):.2f}")
    else:
        print("分位不足，无法计算多空")


def main():
    bt_266 = pd.read_csv("bt_266.csv", encoding="utf-8-sig")
    bt_pit = pd.read_csv("bt_pit.csv", encoding="utf-8-sig")
    task_a(bt_pit)
    print()
    task_b()
    print()
    task_c(bt_pit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
