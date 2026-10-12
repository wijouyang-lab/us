# -*- coding: utf-8 -*-
"""独立实验 ④（CI 版）：用 quant_factor_validation.run_validation 验证因子有效性，并补充对比指标。

CI 调整：sys.path 指向仓库根目录做只读 import；I/O 写入脚本同目录（_temp_experiment/）。
1) 调用 run_validation（路径均指向脚本同目录）→ 产出 IC / 五分位 / 状态。
2) 补充：随机基线（无条件均值收益）、Top-Q 组合 Sharpe / 最大回撤（逐笔近似）。
最终把所有数字 dump 到脚本同目录的 results.json 供报告使用。
"""
import json
import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)  # 只读 import 仓库根目录的 quant 模块
from quant_factor_validation import run_validation
from quant_factor_backtest import assign_quantile, HORIZONS

BT = os.path.join(_HERE, "backtest.csv")
VAL = os.path.join(_HERE, "validation.csv")
CORR = os.path.join(_HERE, "correlation.csv")
REP = os.path.join(_HERE, "report.json")
RES = os.path.join(_HERE, "results.json")


def _max_drawdown(equity):
    eq = np.asarray(equity, dtype=float)
    if eq.size == 0:
        return None
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    return float(dd.min())


def _portfolio_stats(returns, horizon):
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]
    if r.size < 5:
        return None
    mean = float(r.mean())
    std = float(r.std(ddof=1))
    sharpe = float(mean / std * np.sqrt(252.0 / horizon)) if std > 0 else None
    equity = np.cumprod(1.0 + r)
    return {
        "n_positions": int(r.size),
        "mean_return": round(mean, 6),
        "sharpe_annualized": round(sharpe, 4) if sharpe is not None else None,
        "max_drawdown": round(_max_drawdown(equity), 4),
    }


def main():
    if not os.path.exists(BT):
        print(f"缺少 {BT}（run_backtest.py 未生成）。实验中止。")
        sys.exit(0)

    r = run_validation(
        backtest_path=BT,
        validation_path=VAL,
        correlation_path=CORR,
        report_path=REP,
    )
    print("[run_validation] " + str(r))

    bt = pd.read_csv(BT, dtype=str, keep_default_na=False)
    bt_num = bt.copy()
    NON_NUMERIC = {"Technical_Date", "Ticker", "Scan_Date", "schema_version"}
    for c in bt.columns:
        if c in NON_NUMERIC:
            continue
        bt_num[c] = pd.to_numeric(bt[c], errors="coerce")

    val = pd.read_csv(VAL, dtype=str, keep_default_na=False)
    # 仅对数值列做数值化；Factor/Horizon/Status 等字符串列保持原样（避免被 coerce 成 NaN）
    NUM_COLS = [
        "N", "Pearson", "Spearman", "Q1_Avg_Return", "Q2_Avg_Return",
        "Q3_Avg_Return", "Q4_Avg_Return", "Q5_Avg_Return",
        "Q1_Win_Rate", "Q2_Win_Rate", "Q3_Win_Rate", "Q4_Win_Rate",
        "Q5_Win_Rate", "Average_Return", "Median_Return", "Std_Return",
    ]
    val_num = val.copy()
    for c in NUM_COLS:
        if c in val_num.columns:
            val_num[c] = pd.to_numeric(val[c], errors="coerce")

    factors = [f for f in val["Factor"].unique() if str(f).strip()]
    results = {
        "factors": factors,
        "horizons": [f"{n}D" for n in HORIZONS],
        "per_factor_horizon": {},
        "baseline": {},
        "top_quintile_portfolio": {},
        "n_total_obs": int(len(bt_num)),
    }

    # 1) 每因子×期限：IC / 五分位 / 状态（来自 validation.csv）
    for _, row in val_num.iterrows():
        key = f"{row['Factor']}|{row['Horizon']}"
        results["per_factor_horizon"][key] = {
            "N": int(row["N"]) if pd.notna(row["N"]) else 0,
            "IC_pearson": row["Pearson"] if pd.notna(row["Pearson"]) else None,
            "IC_spearman": row["Spearman"] if pd.notna(row["Spearman"]) else None,
            "q1_avg": row["Q1_Avg_Return"] if pd.notna(row["Q1_Avg_Return"]) else None,
            "q5_avg": row["Q5_Avg_Return"] if pd.notna(row["Q5_Avg_Return"]) else None,
            "q5_win_rate": row["Q5_Win_Rate"] if pd.notna(row["Q5_Win_Rate"]) else None,
            "monotonicity": str(row.get("Monotonicity", "")),
            "status": str(row.get("Status", "")),
        }

    # 2) 随机基线：无条件均值前瞻收益 + 全部样本组合指标
    for n in HORIZONS:
        col = f"Forward_Return_{n}D"
        all_r = bt_num[col].dropna().values
        results["baseline"][f"{n}D"] = {
            "mean_return": round(float(np.mean(all_r)), 6) if all_r.size else None,
            "win_rate": round(float((all_r > 0).mean() * 100), 2) if all_r.size else None,
            "portfolio": _portfolio_stats(all_r, n),
        }

    # 3) Top-Q（Q5）组合：按日期横截面取前 20%，逐笔近似 Sharpe / 最大回撤
    for factor in factors:
        if factor not in bt_num.columns:
            continue
        results["top_quintile_portfolio"][factor] = {}
        for n in HORIZONS:
            ret_col = f"Forward_Return_{n}D"
            if ret_col not in bt_num.columns:
                continue
            work = bt_num[["Technical_Date", factor, ret_col]].dropna(
                subset=[factor, ret_col]
            ).copy()
            if "Technical_Date" in work.columns:
                work["_q"] = work.groupby("Technical_Date", group_keys=False)[factor].apply(
                    lambda g: assign_quantile(g, 5)
                )
            else:
                work["_q"] = assign_quantile(work[factor], 5)
            top = work[work["_q"] == "Q5"].sort_values("Technical_Date")
            results["top_quintile_portfolio"][factor][f"{n}D"] = _portfolio_stats(
                top[ret_col].values, n
            )

    with open(RES, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"已写出结果摘要到 {RES}")
    print(f"因子数={len(factors)}，总观测={results['n_total_obs']}")


if __name__ == "__main__":
    main()
