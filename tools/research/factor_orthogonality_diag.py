#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A 线：因子正交性诊断 + 单因子 vs 多因子（岭回归）增量对比。

只读研究脚本：
  输入  research_factor_snapshots_sp500_pit_2y.csv（22 列 PIT 快照）
        research_backtest_sp500_pit_2y.csv（含 Forward_Return_5D）
  输出  docs/FACTOR_ORTHOGONALITY_DIAG.md

核心问题：
  1) 17 个因子彼此冗余吗？（|Spearman| > 0.7 的对 / VIF > 10）
  2) 多因子（岭回归）相比 ATR_Pct 单因子，R² 是否有实质提升？

用法：python tools/research/factor_orthogonality_diag.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
SNAP = REPO / "research_factor_snapshots_sp500_pit_2y.csv"
BT = REPO / "research_backtest_sp500_pit_2y.csv"
OUT = REPO / "docs" / "FACTOR_ORTHOGONALITY_DIAG.md"

FACTORS = [
    "Momentum_5D_Pct", "Momentum_20D_Pct", "Momentum_60D_Pct",
    "Realized_Volatility_20D_Pct", "Volume_Ratio_20D", "ZScore_20D",
    "Beta_60D_SPY", "Stock_RS_20D_vs_SPY",
    "RSI", "MA20", "MA50", "MA20_Slope_Pct_5D", "ATR_Pct",
    "乖离率(%)", "MACD_HIST_LAST", "KDJ_J", "量比",
]
TARGET = "Forward_Return_5D"
CORR_TH = 0.7
VIF_TH = 10.0
ALPHAS = [0.01, 0.1, 1.0]
SAMPLE = 200_000          # 控制内存/耗时；全量约 22 万行


def load():
    if not SNAP.exists():
        raise SystemExit(f"missing: {SNAP}")
    print(f"loading {SNAP.name} …")
    snap = pd.read_csv(SNAP, dtype=str, keep_default_na=False)
    print(f"  snapshot rows={len(snap)} cols={len(snap.columns)}")

    if not BT.exists():
        raise SystemExit(f"missing target source: {BT}")
    print(f"loading {BT.name} …")
    bt = pd.read_csv(BT, dtype=str, keep_default_na=False,
                     usecols=["Ticker", "Technical_Date", TARGET])
    key = ["Ticker", "Technical_Date"]
    df = snap.merge(bt, on=key, how="inner", suffixes=("", "_bt"))
    print(f"  merged rows={len(df)}")

    cols = [f for f in FACTORS if f in df.columns] + [TARGET]
    d = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
    if len(d) > SAMPLE:
        d = d.sample(SAMPLE, random_state=42).reset_index(drop=True)
    print(f"  usable rows={len(d)}  factors={len(cols) - 1}")
    return d, [f for f in FACTORS if f in d.columns]


def vif_table(X: pd.DataFrame) -> pd.Series:
    """逐个因子对其余因子做 OLS（含截距）取 R² → VIF = 1/(1-R²)。"""
    out = {}
    Z = (X - X.mean()) / X.std(ddof=0).replace(0, np.nan)
    Z = Z.fillna(0.0).to_numpy(float)
    n, k = Z.shape
    for j in range(k):
        y = Z[:, j]
        A = np.delete(Z, j, axis=1)
        A = np.column_stack([np.ones(n), A])
        beta, *_ = np.linalg.lstsq(A, y, rcond=None)
        resid = y - A @ beta
        ss_res = float(resid @ resid)
        ss_tot = float(y @ y)
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        r2 = min(max(r2, 0.0), 0.999999)
        out[X.columns[j]] = 1.0 / (1.0 - r2)
    return pd.Series(out).sort_values(ascending=False)


def ols_r2(X: np.ndarray, y: np.ndarray) -> tuple[float, np.ndarray]:
    A = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    resid = y - A @ beta
    ss_res = float(resid @ resid)
    ss_tot = float((y - y.mean()) @ (y - y.mean()))
    return (1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0), beta[1:]


def ridge_r2(X: np.ndarray, y: np.ndarray, alpha: float) -> tuple[float, np.ndarray]:
    n, k = X.shape
    Xc = X - X.mean(axis=0)
    yc = y - y.mean()
    A = Xc.T @ Xc + alpha * n * np.eye(k)
    beta = np.linalg.solve(A, Xc.T @ yc)
    resid = yc - Xc @ beta
    ss_res = float(resid @ resid)
    ss_tot = float(yc @ yc)
    return (1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0), beta


def main() -> int:
    d, factors = load()
    y = d[TARGET].to_numpy(float)

    # ---------------- 1) Spearman 相关 ----------------
    print("\n[1] Spearman 相关矩阵 …")
    corr = d[factors].corr(method="spearman")
    pairs = []
    for i, a in enumerate(factors):
        for b in factors[i + 1:]:
            v = corr.loc[a, b]
            if pd.notna(v) and abs(v) > CORR_TH:
                pairs.append((a, b, float(v)))
    pairs.sort(key=lambda x: -abs(x[2]))
    print(f"  |rho|>{CORR_TH} pairs = {len(pairs)}")

    atr_row = corr["ATR_Pct"].drop(labels=["ATR_Pct"]).sort_values(
        key=lambda s: s.abs(), ascending=False)
    print("  ATR_Pct top-5 |rho|:")
    for k, v in atr_row.head(5).items():
        print(f"    {k:32s} {v:+.3f}")

    # ---------------- 2) VIF ----------------
    print("\n[2] VIF …")
    vifs = vif_table(d[factors])
    high_vif = vifs[vifs > VIF_TH]
    print(f"  VIF>{VIF_TH}: {len(high_vif)} 个")
    for k, v in vifs.head(8).items():
        print(f"    {k:32s} {v:8.2f}")

    # ---------------- 3) 单因子 vs 岭回归 ----------------
    print("\n[3] 回归对比 …")
    Xs = d[factors].to_numpy(float)
    mu, sd = Xs.mean(axis=0), Xs.std(axis=0)
    sd[sd == 0] = 1.0
    Xz = (Xs - mu) / sd

    atr_idx = factors.index("ATR_Pct")
    r2_single, coef_single = ols_r2(Xz[:, [atr_idx]], y)
    print(f"  A) ATR_Pct 单因子 OLS : R²={r2_single:.6f}  beta={coef_single[0]:+.6f}")

    best = None
    for a in ALPHAS:
        r2, beta = ridge_r2(Xz, y, a)
        print(f"  B) Ridge alpha={a:<5} R²={r2:.6f}")
        if best is None or r2 > best[1]:
            best = (a, r2, beta)
    alpha_best, r2_ridge, beta_best = best
    order = np.argsort(-np.abs(beta_best))
    top5 = [(factors[i], float(beta_best[i])) for i in order[:5]]
    lift = r2_ridge - r2_single
    print(f"  → best alpha={alpha_best}  R²={r2_ridge:.6f}  lift={lift:+.6f}")
    print("  Top5 |beta|: " + ", ".join(f"{k}({v:+.4f})" for k, v in top5))

    # ---------------- 4) 报告 ----------------
    OUT.parent.mkdir(parents=True, exist_ok=True)
    L = []
    L.append("# 因子正交性诊断报告（S&P500 PIT 2Y）\n")
    L.append(f"> 自动生成于 `tools/research/factor_orthogonality_diag.py`")
    L.append(f"> 样本：`{SNAP.name}` ∩ `{BT.name}`（target=`{TARGET}`）")
    L.append(f"> 可用行数：**{len(d):,}**（含 {len(factors)} 个因子）\n")

    L.append("## 1. 高相关因子对（|Spearman ρ| > 0.7）\n")
    if pairs:
        L.append("| 因子 A | 因子 B | ρ |\n|---|---|---|")
        for a, b, v in pairs:
            L.append(f"| `{a}` | `{b}` | **{v:+.3f}** |")
    else:
        L.append("无 —— 所有因子对 |ρ| ≤ 0.7。")
    L.append("")

    L.append("## 2. VIF（方差膨胀因子 > 10 视为严重共线）\n")
    L.append("| 因子 | VIF | 判定 |\n|---|---|---|")
    for k, v in vifs.items():
        L.append(f"| `{k}` | {v:.2f} | {'⚠️ >10' if v > VIF_TH else 'ok'} |")
    L.append(f"\n**VIF > 10 的因子数：{len(high_vif)}**\n")

    L.append("## 3. 单因子 vs 多因子（岭回归）\n")
    L.append("| 模型 | R² | 说明 |\n|---|---|---|")
    L.append(f"| A) `ATR_Pct` 单因子 OLS | **{r2_single:.6f}** | 基准 |")
    L.append(f"| B) 全因子 Ridge（α={alpha_best}） | **{r2_ridge:.6f}** | 17 因子 |")
    L.append(f"\n**R² 增量 = {lift:+.6f}**（相对提升 "
             f"{(lift / r2_single * 100 if r2_single > 0 else float('nan')):.1f}%）\n")

    L.append(f"### Top 5 重要特征（Ridge α={alpha_best}，标准化系数）\n")
    L.append("| 因子 | β（标准化） |\n|---|---|")
    for k, v in top5:
        L.append(f"| `{k}` | {v:+.6f} |")
    L.append("")

    L.append("### ATR_Pct 与其最相关的 5 个因子\n")
    L.append("| 因子 | Spearman ρ |\n|---|---|")
    for k, v in atr_row.head(5).items():
        L.append(f"| `{k}` | {v:+.3f} |")
    L.append("")

    L.append("## 4. 结论\n")
    if len(pairs) == 0 and len(high_vif) == 0:
        L.append("- ✅ 因子间无强共线（无 |ρ|>0.7 对、无 VIF>10）→ **正交性良好**。")
    else:
        L.append(f"- ⚠️ 存在 **{len(pairs)}** 对高相关因子、**{len(high_vif)}** 个 VIF>10 因子 → **存在冗余**。")
    if lift > 0.01:
        L.append(f"- ✅ 多因子 R² 相比 ATR_Pct 单因子提升 **{lift:.4f}** → **有增量解释力**。")
    elif lift > 0.001:
        L.append(f"- ○ 提升仅 **{lift:.4f}** → **边际，需谨慎**。")
    else:
        L.append(f"- ✗ 提升仅 **{lift:.6f}** → **几乎无增量**（ATR_Pct 已解释绝大部分）。")
    L.append(f"- 注意：R² 极低（~{r2_ridge:.4f}）属日频因子常态；R² 提升 ≠ 可交易 alpha。")
    L.append("")

    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"\nwritten: {OUT} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
