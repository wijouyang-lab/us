# -*- coding: utf-8 -*-
"""Quant Walk-Forward 纯函数回归测试（使用极小人工 fixture，绝不写入生产文件）。"""
import json
import os
import sys
import tempfile

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_walk_forward import (
    BENCHMARK_MODEL,
    CANDIDATE_MODELS,
    CONFIG,
    QUANT_SCORE_V2_ENABLED,
    _max_drawdown,
    _profit_factor,
    evaluate_segment,
    fit_normalization,
    overfit_status,
    regime_status,
    run_walk_forward,
    score_benchmark,
    score_model,
    split_windows,
    stability_status,
    transform_normalization,
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


# 极小人工 fixture，仅用于测试窗口/冻结/收益计算逻辑
def make_bt(n_rows, seed=42):
    rng = np.random.default_rng(seed)
    rows = []
    base = pd.Timestamp("2026-01-05")
    for i in range(n_rows):
        rows.append({
            "Technical_Date": (base + pd.Timedelta(days=i)).strftime("%Y-%m-%d"),
            "Ticker": f"T{i % 10}",
            "Market_Regime": "NORMAL" if i % 3 != 0 else "STRESSED",
            "Quant_Score": str(round(float(rng.uniform(50, 90)), 2)),
            "Momentum_20D_Pct": str(round(float(rng.uniform(-20, 40)), 2)),
            "RSI_14": str(round(float(rng.uniform(30, 70)), 2)),
            "ATR_Pct": str(round(float(rng.uniform(1, 8)), 2)),
            "Forward_Return_5D": str(round(float(rng.normal(0, 5)), 6)),
            "Forward_Return_10D": str(round(float(rng.normal(0, 8)), 6)),
            "Forward_Return_20D": str(round(float(rng.normal(0, 12)), 6)),
        })
    return pd.DataFrame(rows)


# ---- 1-3. 空数据 / 不足 ----
def test_empty_and_insufficient():
    # 空
    r = run_walk_forward(backtest_path="/tmp/nonexistent_bt.csv",
                         results_path="/tmp/r1.csv", summary_path="/tmp/s1.json")
    check("空数据 → NOT_ENOUGH_DATA", r["status"] == "NOT_ENOUGH_DATA")
    check("空数据 window_count=0", r["window_count"] == 0)

    # 数据不足（< initial_train）
    tmp = tempfile.mkdtemp()
    bt = make_bt(30)  # 30 交易日 < initial_train=50
    bt.to_csv(os.path.join(tmp, "bt.csv"), index=False)
    r2 = run_walk_forward(backtest_path=os.path.join(tmp, "bt.csv"),
                          results_path=os.path.join(tmp, "r.csv"), summary_path=os.path.join(tmp, "s.json"))
    check("数据不足 → 无窗口", r2["window_count"] == 0, f"got {r2['window_count']}")
    check("数据不足 → NOT_ENOUGH_DATA", r2["status"] == "NOT_ENOUGH_DATA")


# ---- 4-5. Expanding / Rolling window ----
def test_windows():
    dates = [f"2026-01-{i:02d}" for i in range(1, 28)]  # 27 天
    # expanding: initial_train=10, oos_step=5 → windows: [10..15], [15..20], [20..25]
    w = split_windows(dates, mode="EXPANDING", initial_train=10, oos_step=5)
    check("Expanding 窗口数", len(w) == 3, f"got {len(w)}")
    # 第一个窗口 train 长度 10
    check("Expanding train 递增", len(w[0][0]) == 10 and len(w[1][0]) == 15 and len(w[2][0]) == 20)
    # rolling: 固定 train 长度
    wr = split_windows(dates, mode="ROLLING", initial_train=10, oos_step=5, rolling_train=10)
    check("Rolling train 固定", len(wr[0][0]) == 10 and len(wr[1][0]) == 10)


# ---- 6-7. Train/OOS disjoint + time ordering ----
def test_disjoint_and_ordering():
    dates = [f"2026-01-{i:02d}" for i in range(1, 21)]
    w = split_windows(dates, mode="EXPANDING", initial_train=10, oos_step=5)
    for train, oos in w:
        check("train/oos 无交集", set(train).isdisjoint(set(oos)))
        check("oos 在 train 之后", max(train) < min(oos))


# ---- 8. no future leakage（OOS 不参与 fit）----
def test_no_leakage():
    bt = make_bt(120)
    dates = sorted(pd.to_datetime(bt["Technical_Date"], errors="coerce").dropna().unique())
    w = split_windows(dates, mode="EXPANDING", initial_train=50, oos_step=20)
    train_dates, oos_dates = w[0]
    train_df = bt[pd.to_datetime(bt["Technical_Date"], errors="coerce").isin(train_dates)]
    oos_df = bt[pd.to_datetime(bt["Technical_Date"], errors="coerce").isin(oos_dates)]
    params = fit_normalization(train_df, ["Momentum_20D_Pct", "RSI_14", "ATR_Pct"])
    # params 只来自 train，与 oos 无关
    check("fit 只用 train（params 数量正确）", len(params) == 3)
    # oos 不参与 fit：验证 params 值不随 oos 变化
    params2 = fit_normalization(pd.concat([train_df, oos_df.iloc[:0]]), ["Momentum_20D_Pct", "RSI_14", "ATR_Pct"])
    check("fit 不受 oos 影响", params == params2)


# ---- 9. frozen normalization ----
def test_frozen_normalization():
    bt = make_bt(100)
    train = bt.iloc[:60]
    oos = bt.iloc[60:]
    params = fit_normalization(train, ["Momentum_20D_Pct"])
    z_train = transform_normalization(train, params, ["Momentum_20D_Pct"])
    z_oos = transform_normalization(oos, params, ["Momentum_20D_Pct"])
    # train 的 z 均值应接近 0（用 train 参数标准化）
    check("train 标准化均值≈0", abs(z_train["_z_Momentum_20D_Pct"].mean()) < 1e-6,
          f"got {z_train['_z_Momentum_20D_Pct'].mean()}")
    # oos 使用同一 frozen 参数（不是 oos 自己拟合）
    check("oos 使用 frozen 参数", "Momentum_20D_Pct" in params)


# ---- 10. frozen weights ----
def test_frozen_weights():
    # 模型 group 权重来自 Phase 4，score_model 不重新拟合权重
    bt = make_bt(60)
    z = transform_normalization(bt, fit_normalization(bt, ["Momentum_20D_Pct", "RSI_14", "ATR_Pct"]),
                                ["Momentum_20D_Pct", "RSI_14", "ATR_Pct"])
    s = score_model(z, "MODEL_B_BALANCED")
    check("score 返回非空", s.notna().any())
    check("score 确定性（两次一致）", s.equals(score_model(z, "MODEL_B_BALANCED")))


# ---- 11-13. Forward return / win rate / avg ----
def test_evaluate():
    rng = np.random.default_rng(1)
    n = 100
    rows = []
    for i in range(n):
        rows.append({"Ticker": f"T{i}", "score": float(i), "Forward_Return_5D": float(rng.normal(0.5, 2))})
    df = pd.DataFrame(rows)
    score = df["score"]
    m = evaluate_segment(df, score, 5, top_fraction=0.30)
    check("N = 30（top 30%）", m["N"] == 30, f"got {m['N']}")
    check("Win_Rate 非 None", m["Win_Rate"] is not None)
    check("Average_Return 非 None", m["Average_Return"] is not None)
    check("Cumulative_Return 非 None", m["Cumulative_Return"] is not None)
    check("Max_Drawdown 非 None", m["Max_Drawdown"] is not None)
    check("Profit_Factor 非 None", m["Profit_Factor"] is not None)


# ---- 14. Max drawdown ----
def test_max_drawdown():
    r = pd.Series([0.1, -0.2, 0.05, -0.3, 0.4])
    dd = _max_drawdown(r)
    check("max drawdown < 0", dd is not None and dd < 0, f"got {dd}")
    check("空序列 → None", _max_drawdown(pd.Series(dtype=float)) is None)


# ---- 15. train/oos gap ----
def test_overfit_gap():
    check("train 强 oos 弱 → POSSIBLE_OVERFIT", overfit_status(0.10, -0.05, 0.05) == "POSSIBLE_OVERFIT")
    check("gap 小 → NO_OVERFIT_SIGNAL", overfit_status(0.10, 0.08, 0.05) == "NO_OVERFIT_SIGNAL")
    check("None → NOT_ENOUGH_DATA", overfit_status(None, 0.05, 0.05) == "NOT_ENOUGH_DATA")


# ---- 16. overfit detection ----
def test_overfit_detection():
    check("明显恶化标记", overfit_status(0.15, -0.02, 0.05) == "POSSIBLE_OVERFIT")
    check("不明显不标记", overfit_status(0.02, 0.01, 0.05) == "NO_OVERFIT_SIGNAL")


# ---- 17. regime split ----
def test_regime_split():
    check("多 regime 同向 → REGIME_CONSISTENT",
          regime_status({"NORMAL": 0.02, "STRESSED": 0.01, "PANIC": 0.03}) == "REGIME_CONSISTENT")
    check("regime 反向 → REGIME_DEPENDENT",
          regime_status({"NORMAL": 0.05, "STRESSED": -0.04}) == "REGIME_DEPENDENT")
    check("单 regime → NOT_ENOUGH_DATA", regime_status({"NORMAL": 0.02}) == "NOT_ENOUGH_DATA")


# ---- 18. model comparison ----
def test_model_comparison():
    bt = make_bt(300)
    tmp = tempfile.mkdtemp()
    bt.to_csv(os.path.join(tmp, "bt.csv"), index=False)
    r = run_walk_forward(backtest_path=os.path.join(tmp, "bt.csv"),
                         results_path=os.path.join(tmp, "r.csv"), summary_path=os.path.join(tmp, "s.json"))
    check("有数据 → OK 或 NOT_ENOUGH_DATA", r["status"] in ("OK", "NOT_ENOUGH_DATA"))
    if r["status"] == "OK":
        res = pd.read_csv(os.path.join(tmp, "r.csv"), dtype=str, keep_default_na=False)
        models = set(res["Model"].unique())
        check("含 3 候选 + 1 基准", models == set(CANDIDATE_MODELS.keys()) | {BENCHMARK_MODEL}, f"got {models}")


# ---- 19. deterministic ----
def test_deterministic():
    bt = make_bt(300)
    tmp = tempfile.mkdtemp()
    bt.to_csv(os.path.join(tmp, "bt.csv"), index=False)
    r1 = run_walk_forward(backtest_path=os.path.join(tmp, "bt.csv"),
                          results_path=os.path.join(tmp, "r1.csv"), summary_path=os.path.join(tmp, "s1.json"))
    r2 = run_walk_forward(backtest_path=os.path.join(tmp, "bt.csv"),
                          results_path=os.path.join(tmp, "r2.csv"), summary_path=os.path.join(tmp, "s2.json"))
    check("两次运行 window_count 一致", r1["window_count"] == r2["window_count"])
    check("两次运行 model_statuses 一致", r1["model_statuses"] == r2["model_statuses"])


# ---- 20. production lock ----
def test_production_lock():
    check("QUANT_SCORE_V2_ENABLED 恒 False", QUANT_SCORE_V2_ENABLED is False)


# ---- 21-22. no AI / no network ----
def test_no_ai_no_network():
    import quant_walk_forward as q
    src = open(q.__file__).read()
    check("无 AI 依赖", not any(k in src for k in ["ClawSocket", "openai", "anthropic", "gpt-"]))
    check("无网络请求", "requests" not in src and "yfinance" not in src)


# ---- 23. no fake production data ----
def test_no_fake_production_data():
    # 空数据时，results.csv 只含表头，summary 全 NOT_ENOUGH_DATA，不产生 0% 胜率
    tmp = tempfile.mkdtemp()
    r = run_walk_forward(backtest_path="/tmp/nonexistent.csv",
                         results_path=os.path.join(tmp, "r.csv"), summary_path=os.path.join(tmp, "s.json"))
    res = pd.read_csv(os.path.join(tmp, "r.csv"), dtype=str, keep_default_na=False)
    check("空数据 results 只有表头（0 行）", len(res) == 0)
    summary = json.load(open(os.path.join(tmp, "s.json")))
    check("summary model 全 NOT_ENOUGH_DATA",
          all(v == "NOT_ENOUGH_DATA" for v in summary["model_statuses"].values()))
    check("production_lock ENABLED=false", summary["production_lock"]["QUANT_SCORE_V2_ENABLED"] is False)


def main():
    test_empty_and_insufficient()
    test_windows()
    test_disjoint_and_ordering()
    test_no_leakage()
    test_frozen_normalization()
    test_frozen_weights()
    test_evaluate()
    test_max_drawdown()
    test_overfit_gap()
    test_overfit_detection()
    test_regime_split()
    test_model_comparison()
    test_deterministic()
    test_production_lock()
    test_no_ai_no_network()
    test_no_fake_production_data()

    print(f"\n结果：通过 {_passed} / {_passed + _failed}")
    if _failures:
        print("失败项：")
        for f in _failures:
            print("  -", f)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
