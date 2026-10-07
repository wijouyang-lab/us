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



def check(name, cond, detail=""):
    """断言：FAIL 时抛出 AssertionError（pytest 可捕获），同时保留打印。"""
    if cond:
        print(f"  [PASS] {name}")
        return True
    print(f"  [FAIL] {name}  {detail}")
    raise AssertionError(f"{name}  {detail}".strip())


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

    # R1（STEP 3-C）：无数据 → 绝不落文件
    check("无 backtest → validation.csv 未创建", not os.path.exists(v_path))
    check("无 backtest → report.json 未创建", not os.path.exists(r_path))
    check("无 backtest → written=False", res.get("written") is False)

    # 空 backtest
    pd.DataFrame(columns=["RSI_14", "Forward_Return_5D"]).to_csv(bt_path, index=False)
    res2 = run_validation(backtest_path=bt_path, validation_path=v_path, correlation_path=c_path, report_path=r_path)
    check("空 backtest → NOT_ENOUGH_DATA", res2["status"] == "NOT_ENOUGH_DATA")
    # R1：空数据同样不落文件（旧行为会写 72 行全 NOT_ENOUGH_DATA 的表）
    check("空 backtest → validation.csv 未创建", not os.path.exists(v_path))
    check("空 backtest → correlation.csv 未创建", not os.path.exists(c_path))
    check("空 backtest → report.json 未创建", not os.path.exists(r_path))
    # 内存态仍可校验"不伪造"：直接调用纯函数确认 N=0 时指标为 None 而非 0
    one = validate_factor_horizon(None, "RSI_14", 5)
    check("N=0 时 Win_Rate 为 None（非 0）", one["Win_Rate"] is None, str(one["Win_Rate"]))
    check("N=0 时 Status=NOT_ENOUGH_DATA", one["Status"] == "NOT_ENOUGH_DATA")

    # 有真实数据 → OK
    make_bt(60).to_csv(bt_path, index=False)
    res3 = run_validation(backtest_path=bt_path, validation_path=v_path, correlation_path=c_path, report_path=r_path)
    check("有数据 → OK", res3["status"] == "OK", f"got {res3['status']}")
    import json
    report = json.load(open(r_path))
    check("report 含 data_maturity", "data_maturity" in report)
    check("report 含 validation_status", "validation_status" in report)
    check("report 含 insufficient_data_reasons", "insufficient_data_reasons" in report)


# ---- STEP 3-C：Phase 3 R1 —— 无数据绝不落文件 ----
def test_no_data_no_files():
    """R1：Phase 3 在三种无数据分支下都必须【不创建任何文件】。

    旧行为会写 72 行全 NOT_ENOUGH_DATA 的 validation.csv —— 文件存在会让人
    误以为验证已完成。现在必须一个文件都不写。
    """
    tmp = tempfile.mkdtemp()
    bt_path = os.path.join(tmp, "quant_factor_backtest.csv")
    v_path = os.path.join(tmp, "quant_factor_validation.csv")
    c_path = os.path.join(tmp, "quant_factor_correlation.csv")
    r_path = os.path.join(tmp, "quant_factor_validation_report.json")

    def none_exist(tag):
        for p, nm in ((v_path, "validation.csv"), (c_path, "correlation.csv"),
                      (r_path, "report.json")):
            check(f"[{tag}] {nm} 未创建", not os.path.exists(p))

    # (a) backtest 不存在
    ra = run_validation(backtest_path=bt_path, validation_path=v_path,
                        correlation_path=c_path, report_path=r_path)
    check("(a) → NOT_ENOUGH_DATA", ra["status"] == "NOT_ENOUGH_DATA")
    check("(a) written=False", ra.get("written") is False)
    none_exist("a 无 backtest")

    # (b) backtest 为空
    pd.DataFrame(columns=["RSI_14", "Forward_Return_5D"]).to_csv(bt_path, index=False)
    rb = run_validation(backtest_path=bt_path, validation_path=v_path,
                        correlation_path=c_path, report_path=r_path)
    check("(b) → NOT_ENOUGH_DATA", rb["status"] == "NOT_ENOUGH_DATA")
    none_exist("b 空 backtest")

    # (c) 有数据 → 正常写出（确认不是"永远不写"）
    make_bt(60).to_csv(bt_path, index=False)
    rc = run_validation(backtest_path=bt_path, validation_path=v_path,
                        correlation_path=c_path, report_path=r_path)
    check("(c) 有数据 → OK", rc["status"] == "OK", f"got {rc['status']}")
    check("(c) written=True", rc.get("written") is True)
    check("(c) validation.csv 已写且非空",
          os.path.exists(v_path) and os.path.getsize(v_path) > 0)

    # (d) 已存在产物 + 后续无数据运行 → 不删除、不截断
    before = open(v_path, "rb").read()
    run_validation(backtest_path=os.path.join(tmp, "missing.csv"),
                   validation_path=v_path, correlation_path=c_path, report_path=r_path)
    check("(d) 已存在产物未被删除/截断", open(v_path, "rb").read() == before)


# ---- STEP 4-8 / Phase 3：validation 状态机全 7 种 status ----
# 约束 1：不硬编码真实事件日期 —— 基准日由 fixture 参数传入（默认用 bdate_range 生成）。
# 约束 2：不假设 Technical_Date 与 price history 一致 —— 日历用独立参数构造。
def _mk_status_df(n, mode="promising", base=None, seed=7):
    """构造可命中指定 validation status 的 backtest DataFrame。

    mode:
      empty       Forward_Return 全空           → NOT_ENOUGH_DATA
      exploratory n 较小(<30)                    → EXPLORATORY
      weak        30<=n<50                       → WEAK_EVIDENCE
      promising   n>=50 + regime 均衡 + 单调     → PROMISING
      inconclusive n>=50 + regime 均衡 + 非单调  → INCONCLUSIVE
      regime      n>=50 + 单一 regime 主导       → REGIME_DEPENDENT:*
    """
    if base is None:
        base = pd.bdate_range("2026-03-02", periods=1)[0]
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        # regime：promising/inconclusive 用均衡分布；regime 模式让 NORMAL 主导
        if mode == "regime":
            regime = "NORMAL" if i < n - 2 else "STRESSED"
        else:
            regime = "NORMAL" if i % 2 == 0 else "STRESSED"
        if mode == "promising":
            f = float(i)                       # 因子升序
            r = float(i) * 0.01                # 收益随因子单调上行
        elif mode == "inconclusive":
            f = float(i)
            r = float(rng.normal(0, 5))        # 与因子无关 → 非单调
        else:
            f = float(rng.uniform(0, 100))
            r = float(rng.normal(0, 5))
        rows.append({
            "Technical_Date": (pd.Timestamp(base) + pd.Timedelta(days=i)).strftime("%Y-%m-%d"),
            "Ticker": "T%d" % (i % 10),
            "Market_Regime": regime,
            "RSI_14": str(round(f, 4)),
            "Momentum_5D_Pct": str(round(f, 4)),
            "Forward_Return_5D": "" if mode == "empty" else str(round(r, 6)),
        })
    return pd.DataFrame(rows)


def test_validation_status_machine():
    """Phase 3 必须能产出全部 7 种 validation status，且阈值边界正确。"""
    cases = [
        ("empty", 60, "NOT_ENOUGH_DATA"),
        ("exploratory", 20, "EXPLORATORY"),
        ("weak", 40, "WEAK_EVIDENCE"),
        ("promising", 60, "PROMISING"),
        ("inconclusive", 60, "INCONCLUSIVE"),
    ]
    for mode, n, expect in cases:
        df = _mk_status_df(n, mode=mode)
        r = validate_factor_horizon(df, "RSI_14", 5)
        check("%-13s N=%-3d → %s" % (mode, n, expect),
              r["Status"] == expect, "got %s (N=%s)" % (r["Status"], r["N"]))

    # REGIME_DEPENDENT：单一 regime 主导(>=80%) 且其它 regime 样本 <5
    r = validate_factor_horizon(_mk_status_df(60, mode="regime"), "RSI_14", 5)
    check("regime 主导 → REGIME_DEPENDENT", str(r["Status"]).startswith("REGIME_DEPENDENT"),
          "got %s" % r["Status"])
    check("Regime_Status 同步标记", str(r["Regime_Status"]).startswith("REGIME_DEPENDENT"),
          str(r["Regime_Status"]))

    # 第 7 种：POTENTIALLY_REDUNDANT 来自因子相关矩阵（|corr|>=0.9）
    n = 40
    base = pd.bdate_range("2026-03-02", periods=1)[0]
    xs = [float(i) for i in range(n)]
    df2 = pd.DataFrame({
        "Technical_Date": [(pd.Timestamp(base) + pd.Timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n)],
        "RSI_14": [str(x) for x in xs],
        # 与 RSI_14 完全线性相关 → Pearson/Spearman = 1.0
        "Momentum_5D_Pct": [str(x * 2.0 + 1.0) for x in xs],
    })
    corr_df, redundant = compute_factor_correlation(df2)
    check("|corr|>=0.9 → 命中冗余对", len(redundant) >= 1, str(len(redundant)))
    check("correlation 标记 POTENTIALLY_REDUNDANT",
          (corr_df["Redundant"] == "POTENTIALLY_REDUNDANT").any(),
          str(corr_df["Redundant"].unique()[:3]))

    # 阈值边界：N=29 → EXPLORATORY；N=30 → 不再是 EXPLORATORY
    r29 = validate_factor_horizon(_mk_status_df(29, mode="weak"), "RSI_14", 5)
    r30 = validate_factor_horizon(_mk_status_df(30, mode="weak"), "RSI_14", 5)
    check("N=29 → EXPLORATORY", r29["Status"] == "EXPLORATORY", "got %s" % r29["Status"])
    check("N=30 → 不再是 EXPLORATORY", r30["Status"] != "EXPLORATORY", "got %s" % r30["Status"])

    # 约束 2：Technical_Date 与"价格日历"不一致时也不得崩溃、不得伪造状态
    df3 = _mk_status_df(60, mode="promising")
    df3["Technical_Date"] = [(pd.Timestamp("2026-01-05") + pd.Timedelta(days=i)).strftime("%Y-%m-%d")
                             for i in range(len(df3))]   # 刻意与基础日历错位
    r3 = validate_factor_horizon(df3, "RSI_14", 5)
    check("日历错位时仍产出合法 status",
          r3["Status"] in ("NOT_ENOUGH_DATA", "EXPLORATORY", "WEAK_EVIDENCE", "PROMISING",
                           "INCONCLUSIVE", "REGIME_DEPENDENT"), str(r3["Status"]))
    check("日历错位时 N 仍真实统计", r3["N"] == 60, str(r3["N"]))


def main():
    _tests = [
        test_empty_data,
        test_n_thresholds,
        test_quintile,
        test_monotonicity,
        test_regime,
        test_correlation,
        test_redundancy,
        test_missing_none,
        test_deterministic,
        test_no_future_leakage,
        test_no_fake_zero,
        test_run_validation_empty,
        # ---- STEP 3-C ----
        test_no_data_no_files,
        # ---- STEP 4-8 / Phase 3 ----
        test_validation_status_machine,
    ]
    _failed = 0
    for _t in _tests:
        try:
            _t()
        except Exception as _e:
            _failed += 1
            print(f"  [FAIL] {_t.__name__}: {_e}")
    print(f"\n结果：通过 {len(_tests) - _failed} / {len(_tests)}")
    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()
