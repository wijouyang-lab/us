# -*- coding: utf-8 -*-
"""
Quant Factor Validation —— 阶段 3：因子有效性验证引擎（纯研究层，非交易层）。

【定位】
    读取 quant_factor_backtest.csv（Phase 2 产出的真实因子 + Forward Return），
    对每个 Raw Factor × Horizon 计算验证指标（N / WinRate / 平均 / 中位 / 标准差 /
    Pearson / Spearman / 五分位 / 单调性 / Regime / 稳定性 / 冗余），
    并输出研究结论（Validation Status）。
    本模块绝不修改 Scan 选股、Quant_Score、Final_Score、Core/Observation 门槛、
    Stop Loss、AI Prompt、Portfolio、Review、Dashboard。

【Strict No-Decision Rule（最高优先级）】
    Phase 3 只产生 Research Evidence（研究证据），绝不自动把任何因子接入生产。
    即使某因子 N=100 且胜率极高，也只能输出 PROMISING，不能 APPROVED，
    不能修改任何生产逻辑、权重、门槛。

【无数据时的严格行为（禁止伪造）】
    - Snapshot=0 或 Forward_Return_ND 无有效观测 → 该 horizon 独立判定为 NOT_ENOUGH_DATA。
    - 禁止：N=0 → Win_Rate=0 / Average_Return=0 / Correlation=0。
    - 禁止：用模拟数据生成报告。
    - 数据不足时只更新状态，绝不制造结果。

【样本量门槛】
    N < 30  → Exploratory Only
    N < 50  → Weak Evidence
    N >= 50 → Usable for preliminary comparison
    N >= 100 → Formal comparison candidate
    （达到 N 门槛 ≠ 因子有效）

【Validation Status 枚举（每个 Factor×Horizon 唯一输出）】
    NOT_ENOUGH_DATA / EXPLORATORY / WEAK_EVIDENCE / PROMISING /
    INCONCLUSIVE / REGIME_DEPENDENT / POTENTIALLY_REDUNDANT

【Monotonicity 判定】
    基于 Q1→Q5 平均收益的相邻差方向：
    - 所有非零相邻差同号            → MONOTONIC
    - 至少 2/3 同号（且差值数>=3） → PARTIAL
    - 其余                           → NON_MONOTONIC
    - 有效 quintile < 3              → NOT_ENOUGH_DATA

【稳定性】按时间顺序切 Early/Middle/Recent，不随机打乱；数据不足 → NOT_ENOUGH_DATA。

【冗余】Raw Factor 间 Pearson/Spearman 相关矩阵，|corr| >= 阈值 → POTENTIALLY_REDUNDANT。
    不自动删除、不自动改权重。
"""

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

from quant_factor_backtest import (
    ALL_FACTORS,
    COMPOSITE_FACTORS,
    EXISTING_SCORE_FACTORS,
    HORIZONS,
    RAW_FACTORS,
    assign_quantile,
    factor_type,
)

VALIDATION_PATH = "quant_factor_validation.csv"
CORRELATION_PATH = "quant_factor_correlation.csv"
REPORT_PATH = "quant_factor_validation_report.json"
BACKTEST_PATH = "quant_factor_backtest.csv"

# 输出 schema 版本（STEP 3-A）：写入 validation.csv / correlation.csv / report.json。
# 命名规则：phase<阶段>.v<主版本>，与 Phase 1–7 完全一致；字段结构变更时递增主版本号。
SCHEMA_VERSION = "phase3.v1"

REDUNDANCY_CORR_THRESHOLD = 0.9  # 高度相关阈值（Pearson 或 Spearman 绝对值）
REGIME_MIN_N = 5                 # 单一 Regime 参与判定所需的最小样本
REGIME_DOMINANCE = 0.8           # 主导 Regime 占比阈值
STABILITY_MIN_TOTAL = 60         # 稳定性判定所需的最小总样本


def _to_float(v):
    try:
        f = float(v)
        if np.isnan(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


# ============================================================================
# 1. Monotonicity（纯函数）
# ============================================================================
def monotonicity_from_quintiles(q_avgs):
    """由 Q1..Q5 平均收益判定单调性。

    q_avgs: 长度 5 的序列，元素为 float 或 None。
    返回 MONOTONIC / PARTIAL / NON_MONOTONIC / NOT_ENOUGH_DATA。
    """
    avgs = [_to_float(v) for v in q_avgs]
    valid = [v for v in avgs if v is not None]
    if len(valid) < 3:
        return "NOT_ENOUGH_DATA"

    diffs = []
    for i in range(1, 5):
        a, b = avgs[i - 1], avgs[i]
        if a is None or b is None:
            continue
        d = b - a
        if abs(d) > 1e-12:
            diffs.append(1 if d > 0 else -1)
    n = len(diffs)
    if n == 0:
        return "NON_MONOTONIC"
    pos = diffs.count(1)
    neg = diffs.count(-1)
    m = max(pos, neg)
    if m == n:
        return "MONOTONIC"
    if n >= 3 and m >= (n * 2 / 3):
        return "PARTIAL"
    return "NON_MONOTONIC"


# ============================================================================
# 2. 单因子 × Horizon 完整验证（纯函数）
# ============================================================================
def validate_factor_horizon(df, factor, horizon):
    """对单个 Factor × Horizon 计算完整验证指标，返回 dict。

    df: quant_factor_backtest.csv 内容（dtype=str，keep_default_na=False）。
    """
    ret_col = f"Forward_Return_{horizon}D"
    result = {
        "Factor": factor,
        "Factor_Type": factor_type(factor),
        "Horizon": f"{horizon}D",
        "N": 0,
        "Status": "NOT_ENOUGH_DATA",
        "Win_Rate": None,
        "Average_Return": None,
        "Median_Return": None,
        "Std_Return": None,
        "Pearson": None,
        "Spearman": None,
        "Q1_Avg_Return": None, "Q2_Avg_Return": None, "Q3_Avg_Return": None,
        "Q4_Avg_Return": None, "Q5_Avg_Return": None,
        "Q1_Win_Rate": None, "Q2_Win_Rate": None, "Q3_Win_Rate": None,
        "Q4_Win_Rate": None, "Q5_Win_Rate": None,
        "Monotonicity": "NOT_ENOUGH_DATA",
        "Regime_Status": "NOT_ENOUGH_DATA",
        "Stability": "NOT_ENOUGH_DATA",
    }

    if df is None or df.empty:
        return result
    if factor not in df.columns or ret_col not in df.columns:
        return result

    work = pd.DataFrame({
        "f": pd.to_numeric(df[factor], errors="coerce"),
        "r": pd.to_numeric(df[ret_col], errors="coerce"),
    })
    if "Technical_Date" in df.columns:
        work["_date"] = pd.to_datetime(df["Technical_Date"], errors="coerce")
    if "Market_Regime" in df.columns:
        work["_regime"] = df["Market_Regime"].astype(str)

    valid = work.dropna(subset=["r"]).copy()  # 无 forward return 的样本不进入统计
    result["N"] = int(len(valid))
    if valid.empty:
        return result

    r = valid["r"]
    pos = int((r > 0).sum())
    neg = int((r <= 0).sum())
    result["Win_Rate"] = round(float(pos / len(r) * 100), 2)
    result["Average_Return"] = round(float(r.mean()), 6)
    result["Median_Return"] = round(float(r.median()), 6)
    result["Std_Return"] = round(float(r.std(ddof=1)), 6) if len(r) >= 2 else None

    # 相关系数（需要因子也有值）
    corr_work = valid.dropna(subset=["f"])
    if len(corr_work) >= 3:
        result["Pearson"] = round(float(corr_work["f"].corr(corr_work["r"])), 4)
        result["Spearman"] = round(float(corr_work["f"].corr(corr_work["r"], method="spearman")), 4)

    # 五分位（全局横截面）
    q = assign_quantile(valid["f"], 5)
    valid = valid.copy()
    valid["_q"] = q
    q_avgs = [None] * 5
    q_wins = [None] * 5
    for i, label in enumerate(["Q1", "Q2", "Q3", "Q4", "Q5"]):
        g = valid[valid["_q"] == label]
        if g.empty:
            continue
        gr = g["r"]
        q_avgs[i] = round(float(gr.mean()), 6)
        q_wins[i] = round(float((gr > 0).mean() * 100), 2)
    result["Q1_Avg_Return"] = q_avgs[0]
    result["Q2_Avg_Return"] = q_avgs[1]
    result["Q3_Avg_Return"] = q_avgs[2]
    result["Q4_Avg_Return"] = q_avgs[3]
    result["Q5_Avg_Return"] = q_avgs[4]
    result["Q1_Win_Rate"] = q_wins[0]
    result["Q2_Win_Rate"] = q_wins[1]
    result["Q3_Win_Rate"] = q_wins[2]
    result["Q4_Win_Rate"] = q_wins[3]
    result["Q5_Win_Rate"] = q_wins[4]
    result["Monotonicity"] = monotonicity_from_quintiles(q_avgs)

    # Regime 分层
    result["Regime_Status"] = _regime_status(valid)

    # 稳定性（时间顺序切分）
    result["Stability"] = _stability(valid)

    # 综合 Status
    result["Status"] = _compose_status(result)
    return result


# ============================================================================
# 3. Regime 判定（纯函数）
# ============================================================================
def _regime_status(valid):
    """判定因子是否 regime 依赖。valid 须含 _regime 列。"""
    if "_regime" not in valid.columns or valid.empty:
        return "NOT_ENOUGH_DATA"
    total = len(valid)
    if total < 30:
        return "NOT_ENOUGH_DATA"
    counts = valid["_regime"].value_counts()
    if counts.empty:
        return "NOT_ENOUGH_DATA"
    top_regime = counts.index[0]
    top_n = int(counts.iloc[0])
    if top_n / total >= REGIME_DOMINANCE:
        # 主导 regime 占比 >= 80%，且其他 regime 样本极少
        others = total - top_n
        if others < REGIME_MIN_N:
            return f"REGIME_DEPENDENT:{top_regime}"
    # 多 regime 分布均衡
    return "MULTI_REGIME"


# ============================================================================
# 4. 稳定性（时间顺序 Early/Middle/Recent，纯函数）
# ============================================================================
def _stability(valid):
    """按时间顺序切三段，比较各段胜率/平均收益/quintile spread。

    返回 STABLE / UNSTABLE / NOT_ENOUGH_DATA。
    """
    if "_date" not in valid.columns or valid.empty:
        return "NOT_ENOUGH_DATA"
    d = valid.dropna(subset=["_date"]).sort_values("_date")
    if len(d) < STABILITY_MIN_TOTAL:
        return "NOT_ENOUGH_DATA"
    n = len(d)
    third = n // 3
    if third < 5:
        return "NOT_ENOUGH_DATA"
    segs = [d.iloc[:third], d.iloc[third:2 * third], d.iloc[2 * third:]]
    win_rates = []
    avg_returns = []
    for seg in segs:
        if seg.empty:
            continue
        r = seg["r"]
        win_rates.append(float((r > 0).mean() * 100))
        avg_returns.append(float(r.mean()))
    if len(win_rates) < 3:
        return "NOT_ENOUGH_DATA"
    # 方向一致性：三段胜率 / 平均收益是否同向
    def _same_sign(vals):
        signs = [1 if v > 0 else (-1 if v < 0 else 0) for v in vals]
        if all(s >= 0 for s in signs) or all(s <= 0 for s in signs):
            return True
        return False
    # 用平均收益的符号一致性 + 胜率波动幅度判断
    wr_spread = max(win_rates) - min(win_rates)
    if wr_spread <= 15.0 and _same_sign(avg_returns):
        return "STABLE"
    return "UNSTABLE"


# ============================================================================
# 5. 综合 Status（纯函数）
# ============================================================================
def _compose_status(result):
    """由各子指标合成 Validation Status。优先级从高到低。"""
    n = result.get("N", 0)
    if n == 0:
        return "NOT_ENOUGH_DATA"
    if n < 30:
        return "EXPLORATORY"
    if n < 50:
        return "WEAK_EVIDENCE"
    # N >= 50
    regime = result.get("Regime_Status", "")
    if isinstance(regime, str) and regime.startswith("REGIME_DEPENDENT"):
        return "REGIME_DEPENDENT"
    mono = result.get("Monotonicity", "")
    if mono == "MONOTONIC":
        return "PROMISING"
    return "INCONCLUSIVE"


# ============================================================================
# 6. 因子冗余（相关矩阵，纯函数）
# ============================================================================
def compute_factor_correlation(df):
    """Raw Factor 之间的 Pearson / Spearman 相关矩阵 + 冗余标记。

    返回 (corr_long_df, redundant_pairs)。
    corr_long_df 列：Factor_A, Factor_B, Pearson, Spearman, Redundant
    """
    rows = []
    redundant = []
    factors = [f for f in RAW_FACTORS if f in df.columns]
    num = pd.DataFrame({f: pd.to_numeric(df[f], errors="coerce") for f in factors})
    for i, fa in enumerate(factors):
        for fb in factors[i + 1:]:
            sub = num[[fa, fb]].dropna()
            pearson = None
            spearman = None
            if len(sub) >= 3:
                pearson = round(float(sub[fa].corr(sub[fb])), 4)
                spearman = round(float(sub[fa].corr(sub[fb], method="spearman")), 4)
            red = False
            if pearson is not None and spearman is not None:
                if abs(pearson) >= REDUNDANCY_CORR_THRESHOLD or abs(spearman) >= REDUNDANCY_CORR_THRESHOLD:
                    red = True
                    redundant.append((fa, fb, pearson, spearman))
            rows.append({
                "Factor_A": fa, "Factor_B": fb,
                "Pearson": pearson, "Spearman": spearman,
                "Redundant": "POTENTIALLY_REDUNDANT" if red else "",
            })
    return pd.DataFrame(rows), redundant


# ============================================================================
# 7. 主入口
# ============================================================================
def compute_validation(backtest_df):
    """计算全部 Factor × Horizon 的验证结果。返回 (validation_df, correlation_df, redundant_pairs)。"""
    vrows = []
    for factor in ALL_FACTORS:
        for n in HORIZONS:
            vrows.append(validate_factor_horizon(backtest_df, factor, n))
    validation_df = pd.DataFrame(vrows)
    corr_df, redundant = compute_factor_correlation(backtest_df)
    return validation_df, corr_df, redundant


def build_report(validation_df, corr_df, redundant_pairs):
    """构造 report JSON dict。"""
    n_factors = len(ALL_FACTORS)
    n_horizons = len(HORIZONS)
    horizon_maturity = {}
    for n in HORIZONS:
        h = f"{n}D"
        sub = validation_df[validation_df["Horizon"] == h]
        max_n = int(sub["N"].max()) if not sub.empty else 0
        horizon_maturity[h] = {
            "max_sample_count": max_n,
            "mature": max_n >= 30,
        }
    status_counts = validation_df["Status"].value_counts().to_dict() if not validation_df.empty else {}
    insufficient = []
    if not validation_df.empty:
        for _, r in validation_df[validation_df["Status"] == "NOT_ENOUGH_DATA"].iterrows():
            insufficient.append({"Factor": r["Factor"], "Horizon": r["Horizon"], "N": int(r["N"])})
    return {
        "schema_version": SCHEMA_VERSION,
        "data_maturity": {
            "backtest_rows": 0,  # 由 run_validation 覆盖
            "n_factors": n_factors,
            "n_horizons": n_horizons,
        },
        "horizon_maturity": horizon_maturity,
        "sample_counts": {
            "max_N_by_horizon": horizon_maturity,
        },
        "validation_status": {
            "status_counts": status_counts,
            "promising": validation_df[validation_df["Status"] == "PROMISING"]["Factor"].tolist()
                         if not validation_df.empty else [],
            "regime_dependent": validation_df[validation_df["Status"] == "REGIME_DEPENDENT"]["Factor"].tolist()
                                if not validation_df.empty else [],
        },
        "redundant_pairs": [{"Factor_A": a, "Factor_B": b, "Pearson": p, "Spearman": s}
                            for a, b, p, s in redundant_pairs],
        "insufficient_data_reasons": insufficient,
        "no_decision_rule": "Phase 3 produces Research Evidence only; no factor is auto-approved for production.",
    }


def run_validation(backtest_path=BACKTEST_PATH,
                   validation_path=VALIDATION_PATH,
                   correlation_path=CORRELATION_PATH,
                   report_path=REPORT_PATH):
    """读 backtest.csv → 验证 → 写三份输出。返回状态 dict。"""
    result = {
        "backtest_rows": 0,
        "status": "NOT_ENOUGH_DATA",
        "validation_rows": 0,
        "correlation_rows": 0,
        "promising": 0,
        # R1 修复：是否真的写出了产物。无数据时保持 False，绝不创建空文件。
        "written": False,
    }

    if not os.path.exists(backtest_path):
        result["reason"] = f"backtest 不存在：{backtest_path}"
        _no_data_skip_write(validation_path, correlation_path, report_path)
        return result

    try:
        bt = pd.read_csv(backtest_path, dtype=str, keep_default_na=False)
    except Exception as e:
        result["reason"] = f"backtest 读取失败：{type(e).__name__}: {e}"
        _no_data_skip_write(validation_path, correlation_path, report_path)
        return result

    result["backtest_rows"] = int(len(bt))
    if bt.empty:
        result["reason"] = "backtest 为空（尚无真实研究数据，绝不做历史回填）"
        _no_data_skip_write(validation_path, correlation_path, report_path)
        return result

    validation_df, corr_df, redundant = compute_validation(bt)
    result["validation_rows"] = int(len(validation_df))
    result["correlation_rows"] = int(len(corr_df))
    result["promising"] = int((validation_df["Status"] == "PROMISING").sum())

    validation_df["schema_version"] = SCHEMA_VERSION
    corr_df["schema_version"] = SCHEMA_VERSION
    validation_df.to_csv(validation_path, index=False, encoding="utf-8")
    corr_df.to_csv(correlation_path, index=False, encoding="utf-8")

    report = build_report(validation_df, corr_df, redundant)
    report["data_maturity"]["backtest_rows"] = result["backtest_rows"]
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    result["status"] = "OK"
    result["written"] = True
    return result


def _no_data_skip_write(validation_path, correlation_path, report_path):
    """R1 防呆修复（STEP 3-C）：无数据时【绝不写出任何文件】。

    旧实现 `_write_empty_outputs()` 会在无数据时写出
    "72 行全 NOT_ENOUGH_DATA 的 validation.csv + 空 correlation.csv + report.json"。
    虽然它标了状态而非伪造结果，但危害与 Phase 2 的空文件同源：
    下游看到"文件存在"可能误以为已完成验证，而实际样本为 0。

    改为：什么都不写，由调用方在 result["reason"] 中说明缺口。
    已存在的产物【不会被删除】——是否覆盖由后续有真实数据的运行决定。
    """
    return None


def main(argv=None):
    """命令行入口（STEP 3-C）：与 Phase 2 一致的退出码语义。

    退出码：0 = OK，或数据不足（NOT_ENOUGH_DATA 是研究数据未就绪的预期状态）；
            1 = --strict 下数据不足，或其它未就绪状态。
    """
    ap = argparse.ArgumentParser(description="Quant Phase 3 · Factor Validation（只读消费 Phase 2 结果）")
    ap.add_argument("--backtest", default=BACKTEST_PATH, help=f"Phase 2 回测 CSV（默认 {BACKTEST_PATH}）")
    ap.add_argument("--validation", default=VALIDATION_PATH, help=f"验证输出 CSV（默认 {VALIDATION_PATH}）")
    ap.add_argument("--correlation", default=CORRELATION_PATH, help=f"相关矩阵输出 CSV（默认 {CORRELATION_PATH}）")
    ap.add_argument("--report", default=REPORT_PATH, help=f"报告输出 JSON（默认 {REPORT_PATH}）")
    ap.add_argument("--strict", action="store_true", help="数据不足时以退出码 1 退出（默认 0）")
    args = ap.parse_args(argv)

    r = run_validation(backtest_path=args.backtest, validation_path=args.validation,
                       correlation_path=args.correlation, report_path=args.report)
    print("[Validation]", r)
    if r["status"] == "OK":
        return 0
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
