# -*- coding: utf-8 -*-
"""
Quant Walk-Forward / Out-of-Sample Validation —— 阶段 5（纯研究层，非交易层）。

【定位】
    验证 Phase 4 Candidate Models 是否能在未见数据上保持表现、是否过拟合、是否跨时间/Regime 稳定。
    本模块绝不修改 Quant_Score、Final_Score、Scan、Review、Portfolio、AI。

【严格禁止数据泄漏】
    - 训练/开发区间只能使用当时已存在的数据。
    - OOS 区间绝不参与：Factor selection / Model selection / Weight fitting /
      Normalization 参数拟合 / Threshold / Cluster / Hyperparameter。
    - OOS 只能用于评价。

【时间序列原则】
    禁止 shuffle / random train-test split / random k-fold。
    只允许 Expanding Window 或 Rolling Window（默认 EXPANDING）。

【第一版训练内容（不引入 ML）】
    1. 归一化参数（winsorized z-score 的 winsor 边界 + mean/std）—— 仅 TRAIN 估计。
    2. 模型 group 权重 —— 使用 Phase 4 已定义的 CANDIDATE_MODELS 权重（冻结，不重估）。
    Phase 5 不重新定义 Phase 4 的 Factor Registry。

【Normalization（frozen）】
    TRAIN → fit（winsor 边界 + mean/std）
    OOS  → transform（使用 frozen TRAIN 参数）
    禁止用 TRAIN + OOS 一起重算。

【Production Lock】
    QUANT_SCORE_V2_ENABLED 恒 false。
    Phase 5 即使 MODEL PASS 也不能 enable，必须 PASS + HUMAN APPROVAL。

【AI / 网络】
    AI Calls = 0，网络请求 = 0。只读已持久化的研究数据。
"""

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

from quant_score_v2 import (
    CANDIDATE_MODELS,
    FACTOR_REGISTRY_DEF,
    QUANT_SCORE_V2_ENABLED,
)

RESULTS_PATH = "quant_walk_forward_results.csv"
SUMMARY_PATH = "quant_walk_forward_summary.json"
BACKTEST_PATH = "quant_factor_backtest.csv"

# ============================================================================
# 配置门槛（集中写进配置，不散落代码）
# ============================================================================
CONFIG = {
    "window_mode": "EXPANDING",       # EXPANDING / ROLLING
    "initial_train_size": 50,         # Expanding 首个 train 长度（交易日数）
    "oos_step": 20,                   # 每个窗口 OOS 长度
    "rolling_train_size": 100,        # Rolling 模式 train 窗口长度
    "min_train_observations": 50,     # 每窗口 train 最低样本
    "min_oos_observations": 20,       # 每窗口 OOS 最低样本
    "min_oos_windows": 1,             # 最低 OOS 窗口数
    "min_valid_horizons": 1,          # 最低有效 horizon 数
    "top_fraction": 0.30,             # 模型"看多组合"占 OOS 横截面比例
    "overfit_gap_threshold": 0.05,     # Train/OOS 收益差（小数比例，0.05=5 个百分点）阈值 → POSSIBLE_OVERFIT
    "winsor_lower": 0.05,             # winsorized z-score 下分位
    "winsor_upper": 0.95,             # winsorized z-score 上分位
}

HORIZONS = (5, 10, 20)
BENCHMARK_MODEL = "CURRENT_EXISTING_QUANT_SCORE"

# 输出 schema 版本（STEP 3-A）：写入 walk_forward results.csv 与 summary.json。
# 命名规则：phase<阶段>.v<主版本>，与 Phase 1–7 完全一致；字段结构变更时递增主版本号。
SCHEMA_VERSION = "phase5.v1"

# factor -> primary group 映射（来自 Phase 4 Registry，不重定义）
FACTOR_GROUP = {f: g for f, g, sg, d, src in FACTOR_REGISTRY_DEF}
RAW_FACTORS = [f for f, g, sg, d, src in FACTOR_REGISTRY_DEF if f != "Quant_Score"]


def _to_float(v):
    try:
        f = float(v)
        if np.isnan(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


# ============================================================================
# 1. Window 切分（纯函数，保持时间顺序，绝不 shuffle）
# ============================================================================
def split_windows(sorted_dates, mode="EXPANDING", initial_train=50, oos_step=20, rolling_train=100):
    """按时间顺序切分 Train/OOS 窗口。

    sorted_dates: 升序唯一日期列表。
    返回 [(train_dates, oos_dates), ...]，train 与 oos 严格不重叠。
    """
    dates = list(sorted_dates)
    n = len(dates)
    windows = []
    if mode == "ROLLING":
        start = initial_train
        while start + oos_step <= n:
            train_start = max(0, start - rolling_train)
            train = dates[train_start:start]
            oos = dates[start:start + oos_step]
            windows.append((train, oos))
            start += oos_step
    else:  # EXPANDING
        start = initial_train
        while start + oos_step <= n:
            train = dates[:start]
            oos = dates[start:start + oos_step]
            windows.append((train, oos))
            start += oos_step
    return windows


# ============================================================================
# 2. 归一化（frozen：train fit → oos transform）
# ============================================================================
def fit_normalization(train_df, factors, lower=0.05, upper=0.95):
    """用 TRAIN 数据估计 winsorized z-score 参数。返回 {factor: (lo, hi, mean, std)}。"""
    params = {}
    for f in factors:
        vals = pd.to_numeric(train_df[f], errors="coerce").dropna() if f in train_df.columns else pd.Series(dtype=float)
        if len(vals) < 10:
            params[f] = None
            continue
        lo = float(vals.quantile(lower))
        hi = float(vals.quantile(upper))
        clipped = vals.clip(lo, hi)
        mean = float(clipped.mean())
        std = float(clipped.std(ddof=1))
        if std is None or np.isnan(std) or std <= 0:
            std = 1.0
        params[f] = (lo, hi, mean, std)
    return params


def transform_normalization(df, params, factors):
    """用 frozen TRAIN 参数 transform 数据。返回标准化后的 DataFrame（新列 _z_<factor>）。"""
    out = df.copy()
    for f in factors:
        p = params.get(f)
        col = f"_z_{f}"
        if p is None or f not in out.columns:
            out[col] = np.nan
            continue
        lo, hi, mean, std = p
        vals = pd.to_numeric(out[f], errors="coerce")
        clipped = vals.clip(lo, hi)
        out[col] = (clipped - mean) / std
    return out


# ============================================================================
# 3. 模型评分（group 权重来自 Phase 4，冻结）
# ============================================================================
def score_model(df_z, model_name):
    """按 Phase 4 定义的 group 权重计算模型得分（冻结，不重估）。"""
    gw = CANDIDATE_MODELS[model_name]["group_weights"]
    # group -> 因子列表（用 z 列）
    group_factors = {}
    for f, g in FACTOR_GROUP.items():
        zcol = f"_z_{f}"
        if zcol in df_z.columns:
            group_factors.setdefault(g, []).append(zcol)
    total_w = 0.0
    score = pd.Series(0.0, index=df_z.index)
    for g, w in gw.items():
        if g not in group_factors:
            continue
        cols = group_factors[g]
        # group 内因子等权（缺失因子按 0 中性处理）
        gscore = df_z[cols].fillna(0.0).mean(axis=1)
        score += w * gscore
        total_w += w
    if total_w > 0:
        score = score / total_w
    return score


def score_benchmark(df):
    """基准模型：直接用现有 Quant_Score（原始值，不做 z-score）。"""
    if "Quant_Score" not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return pd.to_numeric(df["Quant_Score"], errors="coerce")


# ============================================================================
# 4. OOS 评估（纯函数）
# ============================================================================
def evaluate_segment(df, score_series, horizon, top_fraction=0.30):
    """在给定数据段上，按模型 score 选 top-K 看多组合，评估 forward return。

    返回 metrics dict。forward return 缺失（未成熟）的样本不进入统计。
    """
    ret_col = f"Forward_Return_{horizon}D"
    result = {
        "N": 0, "Win_Rate": None, "Average_Return": None, "Median_Return": None,
        "Std_Return": None, "Cumulative_Return": None, "Max_Drawdown": None,
        "Profit_Factor": None,
        "Positive_Return_Count": 0, "Negative_Return_Count": 0,
    }
    if df is None or df.empty or ret_col not in df.columns:
        return result

    work = pd.DataFrame({
        "score": pd.to_numeric(score_series, errors="coerce"),
        "ret": pd.to_numeric(df[ret_col], errors="coerce"),
    })
    work = work.dropna(subset=["ret"]).copy()  # 未成熟 forward return 排除
    work = work.dropna(subset=["score"]).copy()  # 无 score 排除
    if work.empty:
        return result

    n_top = max(1, int(len(work) * top_fraction))
    top = work.nlargest(n_top, "score")
    r = top["ret"]
    result["N"] = int(len(r))
    if r.empty:
        return result
    pos = int((r > 0).sum())
    neg = int((r <= 0).sum())
    result["Positive_Return_Count"] = pos
    result["Negative_Return_Count"] = neg
    result["Win_Rate"] = round(float(pos / len(r) * 100), 2)
    result["Average_Return"] = round(float(r.mean()), 6)
    result["Median_Return"] = round(float(r.median()), 6)
    result["Std_Return"] = round(float(r.std(ddof=1)), 6) if len(r) >= 2 else None
    result["Cumulative_Return"] = round(float((1 + r).prod() - 1), 6)
    result["Max_Drawdown"] = round(float(_max_drawdown(r)), 6)
    result["Profit_Factor"] = _profit_factor(r)
    return result


def _max_drawdown(returns):
    """由收益率序列计算最大回撤（累乘净值峰值回撤）。"""
    if returns is None or len(returns) == 0:
        return None
    equity = (1 + pd.Series(returns)).cumprod()
    peak = equity.cummax()
    dd = (equity - peak) / peak
    return float(dd.min()) if len(dd) else None


def _profit_factor(returns):
    """Profit Factor = Σ正收益 / |Σ负收益|；无负收益 → None（不伪造）。"""
    if returns is None or len(returns) == 0:
        return None
    pos = float(returns[returns > 0].sum())
    neg = float(abs(returns[returns < 0].sum()))
    if neg <= 0:
        return None
    return round(pos / neg, 6)


# ============================================================================
# 5. 过拟合检测 / 稳定性
# ============================================================================
def overfit_status(train_avg, oos_avg, threshold=0.5):
    """Train/OOS 收益差距 → POSSIBLE_OVERFIT / NO_OVERFIT_SIGNAL / NOT_ENOUGH_DATA。"""
    if train_avg is None or oos_avg is None:
        return "NOT_ENOUGH_DATA"
    gap = train_avg - oos_avg
    if gap > threshold:
        return "POSSIBLE_OVERFIT"
    return "NO_OVERFIT_SIGNAL"


def stability_status(seg_returns):
    """由 Early/Middle/Recent 三段收益判断时间稳定性。返回 STABLE / UNSTABLE / NOT_ENOUGH_DATA。"""
    valid = [r for r in seg_returns if r is not None]
    if len(valid) < 2:
        return "NOT_ENOUGH_DATA"
    signs = [1 if r > 0 else (-1 if r < 0 else 0) for r in valid]
    if all(s >= 0 for s in signs) or all(s <= 0 for s in signs):
        return "STABLE"
    return "UNSTABLE"


def regime_status(seg_returns):
    """由各 Regime 收益判断是否 regime 依赖。seg_returns: {regime: avg_return}。"""
    valid = {k: v for k, v in seg_returns.items() if v is not None}
    if len(valid) < 2:
        return "NOT_ENOUGH_DATA"
    signs = {k: (1 if v > 0 else (-1 if v < 0 else 0)) for k, v in valid.items()}
    if len(set(signs.values())) == 1:
        return "REGIME_CONSISTENT"
    return "REGIME_DEPENDENT"


# ============================================================================
# 6. 主入口
# ============================================================================
def load_backtest(path):
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str, keep_default_na=False)
    except Exception:
        return pd.DataFrame()


def run_walk_forward(backtest_path=BACKTEST_PATH, results_path=RESULTS_PATH,
                     summary_path=SUMMARY_PATH, config=None):
    """读 backtest.csv → Walk-Forward 验证 → 写 results.csv 与 summary.json。"""
    cfg = dict(CONFIG)
    if config:
        cfg.update(config)

    result = {
        "backtest_rows": 0,
        "window_count": 0,
        "status": "NOT_ENOUGH_DATA",
        "model_statuses": {},
        # R1 修复：是否真的写出了产物。无数据时保持 False，绝不创建空文件。
        "written": False,
    }

    bt = load_backtest(backtest_path)
    result["backtest_rows"] = int(len(bt))
    if bt.empty:
        _no_data_skip_write(results_path, summary_path, result, "backtest 为空（Snapshot=0，绝不做历史回填）")
        return result

    # 时间排序（保持时间顺序，绝不 shuffle）
    if "Technical_Date" not in bt.columns:
        _no_data_skip_write(results_path, summary_path, result, "缺少 Technical_Date 列")
        return result
    dates = sorted(pd.to_datetime(bt["Technical_Date"], errors="coerce").dropna().unique())

    windows = split_windows(dates, mode=cfg["window_mode"],
                            initial_train=cfg["initial_train_size"],
                            oos_step=cfg["oos_step"],
                            rolling_train=cfg["rolling_train_size"])
    result["window_count"] = len(windows)
    if not windows:
        _no_data_skip_write(results_path, summary_path, result, "Window 数量=0（数据不足）")
        return result

    models = list(CANDIDATE_MODELS.keys()) + [BENCHMARK_MODEL]
    all_rows = []
    model_oos = {m: [] for m in models}  # 收集各模型 OOS 平均收益（用于 summary）

    for wi, (train_dates, oos_dates) in enumerate(windows):
        train_mask = pd.to_datetime(bt["Technical_Date"], errors="coerce").isin(train_dates)
        oos_mask = pd.to_datetime(bt["Technical_Date"], errors="coerce").isin(oos_dates)
        train_df = bt[train_mask]
        oos_df = bt[oos_mask]
        if len(train_df) < cfg["min_train_observations"] or len(oos_df) < cfg["min_oos_observations"]:
            continue

        # frozen normalization：只从 train 估计参数
        params = fit_normalization(train_df, RAW_FACTORS,
                                   lower=cfg["winsor_lower"], upper=cfg["winsor_upper"])
        train_z = transform_normalization(train_df, params, RAW_FACTORS)
        oos_z = transform_normalization(oos_df, params, RAW_FACTORS)

        for model in models:
            if model == BENCHMARK_MODEL:
                train_score = score_benchmark(train_df)
                oos_score = score_benchmark(oos_df)
            else:
                train_score = score_model(train_z, model)
                oos_score = score_model(oos_z, model)

            for h in HORIZONS:
                train_met = evaluate_segment(train_df, train_score, h, top_fraction=cfg["top_fraction"])
                oos_met = evaluate_segment(oos_df, oos_score, h, top_fraction=cfg["top_fraction"])
                gap = None
                if train_met["Average_Return"] is not None and oos_met["Average_Return"] is not None:
                    gap = round(train_met["Average_Return"] - oos_met["Average_Return"], 6)
                of = overfit_status(train_met["Average_Return"], oos_met["Average_Return"],
                                    cfg["overfit_gap_threshold"])

                # 稳定性：OOS 段按时间顺序拆 Early/Middle/Recent
                oos_work = pd.DataFrame({
                    "date": pd.to_datetime(oos_df["Technical_Date"], errors="coerce"),
                    "score": pd.to_numeric(oos_score, errors="coerce"),
                    "ret": pd.to_numeric(oos_df[f"Forward_Return_{h}D"], errors="coerce"),
                }).dropna(subset=["ret", "score"])
                oos_work = oos_work.sort_values("date")
                seg_rets = []
                if len(oos_work) >= 3:
                    third = len(oos_work) // 3
                    for seg in [oos_work.iloc[:third], oos_work.iloc[third:2 * third], oos_work.iloc[2 * third:]]:
                        if seg.empty:
                            seg_rets.append(None)
                            continue
                        n_top = max(1, int(len(seg) * cfg["top_fraction"]))
                        top = seg.nlargest(n_top, "score")
                        seg_rets.append(round(float(top["ret"].mean()), 6) if not top.empty else None)
                stab = stability_status(seg_rets)

                # Regime 稳定性
                regime_work = oos_work.copy()
                regime_work["regime"] = oos_df.loc[regime_work.index, "Market_Regime"].astype(str) \
                    if "Market_Regime" in oos_df.columns else "UNKNOWN"
                reg_rets = {}
                for rg, g in regime_work.groupby("regime"):
                    n_top = max(1, int(len(g) * cfg["top_fraction"]))
                    top = g.nlargest(n_top, "score")
                    reg_rets[rg] = round(float(top["ret"].mean()), 6) if not top.empty else None
                reg_stat = regime_status(reg_rets)

                # Validation Status
                val_status = _validation_status(oos_met, of, cfg)

                all_rows.append({
                    "Model": model,
                    "Window_ID": f"W{wi + 1:03d}",
                    "Train_Start": str(train_dates[0])[:10],
                    "Train_End": str(train_dates[-1])[:10],
                    "OOS_Start": str(oos_dates[0])[:10],
                    "OOS_End": str(oos_dates[-1])[:10],
                    "Horizon": f"{h}D",
                    "Train_N": train_met["N"],
                    "OOS_N": oos_met["N"],
                    "Train_Win_Rate": train_met["Win_Rate"],
                    "OOS_Win_Rate": oos_met["Win_Rate"],
                    "Train_Average_Return": train_met["Average_Return"],
                    "OOS_Average_Return": oos_met["Average_Return"],
                    "Train_Median_Return": train_met["Median_Return"],
                    "OOS_Median_Return": oos_met["Median_Return"],
                    "OOS_Std_Return": oos_met["Std_Return"],
                    "OOS_Cumulative_Return": oos_met["Cumulative_Return"],
                    "OOS_Max_Drawdown": oos_met["Max_Drawdown"],
                    "Train_OOS_Gap": gap,
                    "Market_Regime": "|".join(sorted(reg_rets.keys())),
                    "Stability_Status": stab,
                    "Overfit_Status": of,
                    "Validation_Status": val_status,
                })
                if oos_met["Average_Return"] is not None:
                    model_oos[model].append(oos_met["Average_Return"])

    results_df = pd.DataFrame(all_rows)
    results_df["schema_version"] = SCHEMA_VERSION
    results_df.to_csv(results_path, index=False, encoding="utf-8")
    result["result_rows"] = int(len(results_df))

    # summary
    model_statuses = {}
    for m in models:
        rets = model_oos[m]
        if not rets:
            model_statuses[m] = "NOT_ENOUGH_DATA"
        else:
            model_statuses[m] = _model_verdict(m, rets, results_df, cfg)
    result["model_statuses"] = model_statuses
    result["status"] = "OK" if results_df is not None and not results_df.empty else "NOT_ENOUGH_DATA"

    if results_df is not None and not results_df.empty:
        result["written"] = True

    summary = build_summary(result, results_df, model_statuses, cfg)
    tmp = summary_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    os.replace(tmp, summary_path)
    return result


def _validation_status(oos_met, overfit, cfg):
    """综合 OOS 结果判定 PASS / FAIL / INCONCLUSIVE / NOT_ENOUGH_DATA。"""
    n = oos_met["N"]
    avg = oos_met["Average_Return"]
    if n < cfg["min_oos_observations"]:
        return "NOT_ENOUGH_DATA"
    if avg is None:
        return "NOT_ENOUGH_DATA"
    if overfit == "POSSIBLE_OVERFIT":
        return "INCONCLUSIVE"
    if avg > 0:
        return "PASS"
    return "FAIL"


def _model_verdict(model, oos_rets, results_df, cfg):
    """模型级结论（PASS 只是满足预定义 OOS 条件，不等于 PRODUCTION APPROVED）。"""
    avg = float(np.mean(oos_rets))
    if avg > 0:
        return "PASS"
    if avg <= 0 and all(r is not None for r in oos_rets):
        return "FAIL"
    return "INCONCLUSIVE"


def build_summary(result, results_df, model_statuses, cfg):
    horizon_maturity = {}
    for h in HORIZONS:
        sub = results_df[results_df["Horizon"] == f"{h}D"] if results_df is not None and not results_df.empty else pd.DataFrame()
        oos_n = int(sub["OOS_N"].max()) if not sub.empty else 0
        horizon_maturity[f"{h}D"] = {"max_oos_sample": oos_n, "mature": oos_n >= cfg["min_oos_observations"]}
    return {
        "schema_version": SCHEMA_VERSION,
        "data_maturity": {
            "backtest_rows": result.get("backtest_rows", 0),
            "window_count": result.get("window_count", 0),
        },
        "config": cfg,
        "horizon_maturity": horizon_maturity,
        "model_statuses": model_statuses,
        "oos_sample_by_model": {
            m: int(results_df[results_df["Model"] == m]["OOS_N"].sum())
            if results_df is not None and not results_df.empty else 0
            for m in list(CANDIDATE_MODELS.keys()) + [BENCHMARK_MODEL]
        },
        "not_enough_data_reason": result.get("reason", ""),
        "production_lock": {
            "QUANT_SCORE_V2_ENABLED": bool(QUANT_SCORE_V2_ENABLED),
            "note": "Phase 5 即使 MODEL PASS 也不 enable，必须 PASS + HUMAN APPROVAL。",
        },
        "no_decision_rule": "PASS 仅表示满足预定义 OOS 条件，不等于 PRODUCTION APPROVED。",
    }


def _no_data_skip_write(results_path, summary_path, result, reason):
    """R1 防呆修复（STEP 3-C）：无数据时【绝不写出任何文件】。

    旧实现 `_write_empty_outputs()` 会写出"0 行 results.csv + summary.json"，
    下游看到文件存在可能误以为已完成 OOS 验证，而实际 window_count=0。

    改为：只记录 reason 与模型状态（内存态），不落任何文件。
    已存在的产物【不会被删除】——是否覆盖由后续有真实数据的运行决定。
    """
    result["reason"] = reason
    result["model_statuses"] = {
        m: "NOT_ENOUGH_DATA" for m in list(CANDIDATE_MODELS.keys()) + [BENCHMARK_MODEL]
    }
    result["written"] = False
    return None


def main(argv=None):
    """命令行入口（STEP 3-C）：与 Phase 2 一致的退出码语义。

    退出码：0 = OK，或数据不足（预期状态）；1 = --strict 下数据不足。
    """
    ap = argparse.ArgumentParser(description="Quant Phase 5 · Walk-Forward / OOS（只读消费 Phase 2 结果）")
    ap.add_argument("--backtest", default=BACKTEST_PATH, help=f"Phase 2 回测 CSV（默认 {BACKTEST_PATH}）")
    ap.add_argument("--results", default=RESULTS_PATH, help=f"results 输出（默认 {RESULTS_PATH}）")
    ap.add_argument("--summary", default=SUMMARY_PATH, help=f"summary 输出（默认 {SUMMARY_PATH}）")
    ap.add_argument("--strict", action="store_true", help="数据不足时以退出码 1 退出（默认 0）")
    args = ap.parse_args(argv)

    r = run_walk_forward(backtest_path=args.backtest, results_path=args.results,
                         summary_path=args.summary)
    print("[Walk-Forward]", r)
    if r["status"] == "OK":
        return 0
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
