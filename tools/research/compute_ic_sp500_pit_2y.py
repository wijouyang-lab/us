#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""历史因子 IC 分析（17 因子）—— S&P 500 点内（PIT）版

从 research_factor_snapshots_sp500_pit_2y.csv（22 列，含 17 因子）+
research_backtest_sp500_pit_2y.csv（含 Forward_Return_{5,10,20}D）按
(Ticker, Technical_Date) join，用 pandas .corr(method="spearman") 算 IC
（口径与 quant_factor_backtest.py:259-261 一致）。

铁律：前瞻收益只从 backtest CSV 搬运，绝不自算。
与 S&P500 静态版的唯一差异 = SNAP / BT / OUT 三个文件名。
"""
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
SNAP = REPO / "research_factor_snapshots_sp500_pit_2y.csv"
BT = REPO / "research_backtest_sp500_pit_2y.csv"
OUT = REPO / "research_ic_sp500_pit_2y.csv"

FACTORS = [
    "Momentum_5D_Pct", "Momentum_20D_Pct", "Momentum_60D_Pct",
    "Realized_Volatility_20D_Pct", "Volume_Ratio_20D", "ZScore_20D",
    "Beta_60D_SPY", "Stock_RS_20D_vs_SPY",
    "RSI", "MA20", "MA50", "MA20_Slope_Pct_5D", "ATR_Pct",
    "乖离率(%)", "MACD_HIST_LAST", "KDJ_J", "量比",
]
HORIZONS = (5, 10, 20)


def main():
    if not SNAP.exists():
        print(f"missing: {SNAP}")
        return 1
    if not BT.exists():
        print(f"missing: {BT}")
        return 1

    print(f"loading: {SNAP.name} ({SNAP.stat().st_size} bytes)")
    snap = pd.read_csv(SNAP, dtype=str, keep_default_na=False)
    print(f"  snapshot rows: {len(snap)}, cols: {len(snap.columns)}")

    print(f"loading: {BT.name} ({BT.stat().st_size} bytes)")
    bt = pd.read_csv(BT, dtype=str, keep_default_na=False)
    print(f"  backtest rows: {len(bt)}, cols: {len(bt.columns)}")

    key = ["Ticker", "Technical_Date"]
    ret_cols = [f"Forward_Return_{h}D" for h in HORIZONS]

    missing_in_snap = [k for k in key if k not in snap.columns]
    missing_in_bt = [k for k in key + ret_cols if k not in bt.columns]
    if missing_in_snap:
        print(f"missing key in snapshot: {missing_in_snap}")
        return 1
    if missing_in_bt:
        print(f"missing key/returns in backtest: {missing_in_bt}")
        return 1

    merged = snap.merge(bt[key + ret_cols], on=key, how="inner", suffixes=("", "_bt"))
    print(f"merged rows: {len(merged)}")

    rows = []
    for factor in FACTORS:
        if factor not in merged.columns:
            print(f"  skip (not in merged): {factor}")
            continue
        for h in HORIZONS:
            ret_col = f"Forward_Return_{h}D"
            sub = merged[[factor, ret_col]].copy()
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
