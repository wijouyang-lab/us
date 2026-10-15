#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""历史因子 IC 分析（2 年）

从 research_backtest_2y.csv（含 8 因子 + Forward_Return_{5,10,20}D）自算 IC。
口径严格复用 quant_factor_backtest.py:259-261 的 pandas .corr(method="spearman")。
"""
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
BACKTEST = REPO / "research_backtest_2y.csv"
OUT = REPO / "research_ic_2y.csv"

FACTORS = [
    "Momentum_5D_Pct", "Momentum_20D_Pct", "Momentum_60D_Pct",
    "Realized_Volatility_20D_Pct", "Volume_Ratio_20D", "ZScore_20D",
    "Beta_60D_SPY", "Stock_RS_20D_vs_SPY",
]
HORIZONS = (5, 10, 20)


def main():
    if not BACKTEST.exists():
        print(f"missing: {BACKTEST}")
        return 1

    print(f"loading: {BACKTEST} ({BACKTEST.stat().st_size} bytes)")
    df = pd.read_csv(BACKTEST, dtype=str, keep_default_na=False)
    print(f"rows: {len(df)}")
    print(f"cols: {list(df.columns)}")

    rows = []
    for factor in FACTORS:
        if factor not in df.columns:
            print(f"  skip (not in CSV): {factor}")
            continue
        for h in HORIZONS:
            ret_col = f"Forward_Return_{h}D"
            if ret_col not in df.columns:
                continue
            sub = df[[factor, ret_col]].copy()
            sub[factor] = pd.to_numeric(sub[factor], errors="coerce")
            sub[ret_col] = pd.to_numeric(sub[ret_col], errors="coerce")
            sub = sub.dropna()
            n = len(sub)
            if n < 30:
                rows.append({
                    "Factor": factor, "Horizon": f"{h}D", "N": n,
                    "IC_Spearman": "", "IC_Pearson": "", "P_Value": "",
                    "schema_version": "research.v1",
                })
                continue
            ic_s = float(sub[factor].corr(sub[ret_col], method="spearman"))
            ic_p = float(sub[factor].corr(sub[ret_col]))
            # p 值（显著性标注用，不改 IC 口径）
            try:
                from scipy.stats import spearmanr
                _, pval = spearmanr(sub[factor], sub[ret_col])
                pval = round(float(pval), 6)
            except Exception:
                pval = ""
            rows.append({
                "Factor": factor, "Horizon": f"{h}D", "N": n,
                "IC_Spearman": round(ic_s, 4),
                "IC_Pearson": round(ic_p, 4),
                "P_Value": pval,
                "schema_version": "research.v1",
            })

    out_df = pd.DataFrame(rows)
    out_df.to_csv(OUT, index=False, encoding="utf-8")
    print(f"\nwritten: {OUT} ({len(out_df)} rows)")
    print("\n=== IC 表 ===")
    print(out_df.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
