# -*- coding: utf-8 -*-
"""Quant Factor Validation 纯函数回归测试（不依赖真实数据/网络）。"""
import os
import sys
import tempfile

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_factor_validation import (
    ALL_FACTORS,
    compute_factor_correlation,
    compute_validation,
    monotonicity_from_quintiles,
    run_validation,
    validate_factor_horizon,
)

_passed = 0
_failed = 0
_failures = []


def check(name, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1
    else:
        _failed += 1
        _failures.append(f"{name}  {detail}")
        print(f"  ✗ {name}  {detail}")


def make_bt(n_rows, seed=42, with_regime=True):
    """构造 n_rows 行 backtest 数据（含因子 + Forward_Return + Technical_Date + Market_Regime）。"""
    rng = np.random.default_rng(seed)
    rows = []
    base = pd.Timestamp("2026-01-05")
    for i in range(n_rows):
        r = {
            "Technical_Date": (base + pd.Timedelta(days=i)).strftime("%Y-%m-%d"),
            "Ticker": f"T{i % 10}",
            "RSI_14": str(round(float(rng.uniform(30, 70)), 2)),
            "Bias_Pct": str(round(float(rng.uniform(-5, 15)), 2)),
            "Momentum_5D_Pct": str(round(float(rng.uniform(-10, 20)), 2)),
            "Momentum_20D_Pct": str(round(float(rng.uniform(-20, 40)), 2)),
            "ZScore_20D": str(round(float(rng.uniform(-2, 2)), 2)),
            "Quant_Score": str(round(float(rng.uniform(50, 90)), 2)),
            "Market_Regime": "NORMAL" if i % 3 != 0 else "STRESSED",
            "Forward_Return_5D": str(round(float(rng.normal(0, 5)), 6)),
            "Forward_Return_10D": str(round(float(rng.normal(0, 8)), 6)),
            "Forward_Return_20D": str(round(float(rng.normal(0, 12)), 6)),
        }
        rows.append(r)
    return pd.DataFrame(rows)


# ---- 1. 空数据 ----
def test_empty_data():
    r = validate_factor_horizon(None, "RSI_14", 5)
    check("空数据 N=0", r["N"] == 0, f"got {r['N']}")
    check("空数据 Status=NOT_ENOUGH_DATA", r["Status"] == "NOT_ENOUGH_DATA")
    check("空数据 Win_Rate=None（不是0）", r["Win_Rate"] is None, f"got {r['Win_Rate']}")
    check("空数据 Average=None（不是0）", r["Average_Return"] is None)
    check("空数据 Pearson=None（不是0）", r["Pearson"] is None)


# ---- 2-5. N 门槛 ----
def test_n_thresholds():
    for n_rows, expect in [(10, "EXPLORATORY"), (40, "WEAK_EVIDENCE")]:
        bt = make_bt(n_rows)
        r = validate_factor_horizon(bt, "RSI_14", 5)
        check(f"N={n_rows} → {expect}", r["Status"] == expect, f"got {r['Status']} (N={r['N']})")

    # N>=50 且单调 → PROMISING（需构造单调 + 混合 regime 数据，避免 REGIME_DEPENDENT 干扰）
    rng = np.random.default_rng(1)
    n = 60
    rows = []
    for i in range(n):
        rsi = 30 + i * 0.5
        ret = (rsi - 45) * 0.05 + rng.normal(0, 0.5)
        rows.append({"Technical_Date": f"2026-01-{1 + (i % 20):02d}", "Ticker": f"T{i % 10}",
                     "RSI_14": str(round(rsi, 2)),
                     "Market_Regime": "NORMAL" if i % 2 == 0 else "STRESSED",  # 混合 regime
                     "Forward_Return_5D": str(round(ret, 6))})
    bt = pd.DataFrame(rows)
    r = validate_factor_horizon(bt, "RSI_14", 5)
    check("N=60 单调 → PROMISING 或 INCONCLUSIVE", r["Status"] in ("PROMISING", "INCONCLUSIVE"),
          f"got {r['Status']} (N={r['N']}, regime={r['Regime_Status']})")


# ---- 6. quintile ----
def test_quintile():
    bt = make_bt(100)
    r = validate_factor_horizon(bt, "RSI_14", 5)
    for q in ["Q1_Avg_Return", "Q2_Avg_Return", "Q3_Avg_Return", "Q4_Avg_Return", "Q5_Avg_Return"]:
        check(f"{q} 有值", r[q] is not None, f"got {r[q]}")


# ---- 7. monotonicity ----
def test_monotonicity():
    check("严格单调增 → MONOTONIC", monotonicity_from_quintiles([1, 2, 3, 4, 5]) == "MONOTONIC")
    check("严格单调减 → MONOTONIC", monotonicity_from_quintiles([5, 4, 3, 2, 1]) == "MONOTONIC")
    check("部分反向 → PARTIAL", monotonicity_from_quintiles([1, 2, 1, 3, 4]) == "PARTIAL")
    check("严重反向 → NON_MONOTONIC", monotonicity_from_quintiles([1, 5, 1, 5, 1]) == "NON_MONOTONIC")
    check("有效<3 → NOT_ENOUGH_DATA", monotonicity_from_quintiles([1, 2, None, None, None]) == "NOT_ENOUGH_DATA")
    check("含 None 但有效>=3", monotonicity_from_quintiles([1, 2, 3, None, None]) == "MONOTONIC")


# ---- 8. regime split ----
def test_regime():
    # 构造 regime 主导的数据
    rows = []
    for i in range(100):
        rows.append({"Technical_Date": f"2026-01-{1 + (i % 20):02d}", "Ticker": f"T{i % 10}",
                     "RSI_14": "50", "Market_Regime": "NORMAL" if i < 95 else "PANIC",
                     "Forward_Return_5D": "1.0"})
    bt = pd.DataFrame(rows)
    r = validate_factor_horizon(bt, "RSI_14", 5)
    check("Regime_Status 非空", r["Regime_Status"] != "NOT_ENOUGH_DATA", f"got {r['Regime_Status']}")


# ---- 9-10. Pearson / Spearman ----
def test_correlation():
    rng = np.random.default_rng(7)
    n = 50
    x = np.linspace(30, 70, n)
    rows = []
    for i in range(n):
        rows.append({"Technical_Date": f"2026-01-{1 + (i % 20):02d}", "Ticker": f"T{i % 10}",
                     "RSI_14": str(round(x[i], 2)), "Market_Regime": "NORMAL",
                     "Forward_Return_5D": str(round(x[i] * 0.1 + rng.normal(0, 0.01), 6))})
    bt = pd.DataFrame(rows)
    r = validate_factor_horizon(bt, "RSI_14", 5)
    check("Pearson 接近 1（正相关）", r["Pearson"] is not None and r["Pearson"] > 0.9, f"got {r['Pearson']}")
    check("Spearman 接近 1", r["Spearman"] is not None and r["Spearman"] > 0.9, f"got {r['Spearman']}")


# ---- 11. redundancy ----
def test_redundancy():
    rng = np.random.default_rng(3)
    n = 40
    x = np.linspace(30, 70, n)
    rows = []
    for i in range(n):
        rows.append({"Technical_Date": f"2026-01-{1 + (i % 20):02d}", "Ticker": f"T{i % 10}",
                     "RSI_14": str(round(x[i], 2)),
                     "Bias_Pct": str(round(x[i] * 2 + 10, 2)),  # 与 RSI 高度线性相关
                     "Momentum_5D_Pct": str(round(float(rng.normal(0, 10)), 2)),
                     "Forward_Return_5D": "1.0"})
    bt = pd.DataFrame(rows)
    corr_df, redundant = compute_factor_correlation(bt)
    check("相关矩阵非空", len(corr_df) > 0, f"got {len(corr_df)}")
    # RSI 与 Bias 高度相关 → 应标记 redundant
    red_pairs = [(a, b) for a, b, p, s in redundant]
    check("RSI/Bias 被标记冗余", ("RSI_14", "Bias_Pct") in red_pairs or ("Bias_Pct", "RSI_14") in red_pairs,
          f"got {red_pairs}")


# ---- 12-13. 缺失值 / None ----
def test_missing_none():
    rows = [
        {"Technical_Date": "2026-01-05", "Ticker": "A", "RSI_14": "50", "Market_Regime": "NORMAL", "Forward_Return_5D": ""},
        {"Technical_Date": "2026-01-06", "Ticker": "B", "RSI_14": "", "Market_Regime": "NORMAL", "Forward_Return_5D": "2.0"},
        {"Technical_Date": "2026-01-07", "Ticker": "C", "RSI_14": "60", "Market_Regime": "NORMAL", "Forward_Return_5D": "3.0"},
    ]
    bt = pd.DataFrame(rows)
    r = validate_factor_horizon(bt, "RSI_14", 5)
    # 有效 forward return 有 2 条（B 和 C），C 的 RSI 也有效 → N=2
    check("缺失 forward 不计入 N", r["N"] == 2, f"got {r['N']}")
    # N=2（>0 但 <30）→ EXPLORATORY，而非 NOT_ENOUGH_DATA
    check("N=2 → EXPLORATORY", r["Status"] == "EXPLORATORY", f"got {r['Status']}")


# ---- 14. deterministic repeat ----
def test_deterministic():
    bt = make_bt(80)
    r1 = validate_factor_horizon(bt, "RSI_14", 5)
    r2 = validate_factor_horizon(bt, "RSI_14", 5)
    check("重复运行结果一致", r1 == r2)
    v1, c1, _ = compute_validation(bt)
    v2, c2, _ = compute_validation(bt)
    pd.testing.assert_frame_equal(v1, v2)
    pd.testing.assert_frame_equal(c1, c2)
    check("compute_validation 确定性", True)


# ---- 15. 不允许 future leakage ----
def test_no_future_leakage():
    # 验证引擎只读 Forward_Return 列作为结果，因子不读取 Review/Exit/PnL
    bt = make_bt(30)
    r = validate_factor_horizon(bt, "RSI_14", 5)
    check("结果 dict 不含 Exit/PnL/Review 字段", not any("Exit" in k or "PnL" in k or "Review" in k for k in r))


# ---- 16. 空样本不产生 0% 胜率 ----
def test_no_fake_zero():
    # N=0 时 Win_Rate 必须是 None 而不是 0
    empty = pd.DataFrame(columns=["RSI_14", "Forward_Return_5D", "Technical_Date", "Market_Regime"])
    r = validate_factor_horizon(empty, "RSI_14", 5)
    check("N=0 Win_Rate=None", r["Win_Rate"] is None, f"got {r['Win_Rate']}")
    check("N=0 Average=None", r["Average_Return"] is None)


# ---- 17. 不产生生产假数据（run_validation 无数据时） ----
def test_run_validation_empty():
    tmp = tempfile.mkdtemp()
    bt_path = os.path.join(tmp, "quant_factor_backtest.csv")
    v_path = os.path.join(tmp, "quant_factor_validation.csv")
    c_path = os.path.join(tmp, "quant_factor_correlation.csv")
    r_path = os.path.join(tmp, "quant_factor_validation_report.json")

    # 无 backtest 文件
    res = run_validation(backtest_path=bt_path, validation_path=v_path, correlation_path=c_path, report_path=r_path)
    check("无 backtest → NOT_ENOUGH_DATA", res["status"] == "NOT_ENOUGH_DATA", f"got {res['status']}")

    # 空 backtest
    pd.DataFrame(columns=["RSI_14", "Forward_Return_5D"]).to_csv(bt_path, index=False)
    res2 = run_validation(backtest_path=bt_path, validation_path=v_path, correlation_path=c_path, report_path=r_path)
    check("空 backtest → NOT_ENOUGH_DATA", res2["status"] == "NOT_ENOUGH_DATA")
    # 校验写出的 validation 全是 NOT_ENOUGH_DATA，且 N=0 时 Win_Rate 是空（非0）
    vdf = pd.read_csv(v_path, dtype=str, keep_default_na=False)
    check("空数据 validation 行数 = factor×horizon", len(vdf) == len(ALL_FACTORS) * 3, f"got {len(vdf)}")
    check("所有行 Status=NOT_ENOUGH_DATA", (vdf["Status"] == "NOT_ENOUGH_DATA").all())
    check("N=0 时 Win_Rate 为空", (vdf["Win_Rate"] == "").all())

    # 有真实数据 → OK
    make_bt(60).to_csv(bt_path, index=False)
    res3 = run_validation(backtest_path=bt_path, validation_path=v_path, correlation_path=c_path, report_path=r_path)
    check("有数据 → OK", res3["status"] == "OK", f"got {res3['status']}")
    import json
    report = json.load(open(r_path))
    check("report 含 data_maturity", "data_maturity" in report)
    check("report 含 validation_status", "validation_status" in report)
    check("report 含 insufficient_data_reasons", "insufficient_data_reasons" in report)


def main():
    test_empty_data()
    test_n_thresholds()
    test_quintile()
    test_monotonicity()
    test_regime()
    test_correlation()
    test_redundancy()
    test_missing_none()
    test_deterministic()
    test_no_future_leakage()
    test_no_fake_zero()
    test_run_validation_empty()

    print(f"\n结果：通过 {_passed} / {_passed + _failed}")
    if _failures:
        print("失败项：")
        for f in _failures:
            print("  -", f)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
