# -*- coding: utf-8 -*-
"""
Quant Score 2.0 Framework —— 阶段 4：候选评分模型研究框架（纯研究层，非交易层）。

【定位】
    建立"未来 Quant Score 2.0"的候选模型框架，与当前生产 Quant_Score 完全分离保存。
    本模块绝不修改 Scan 选股、Quant_Score、Final_Score、Core/Observation 门槛、
    Stop Loss、AI、Portfolio、Review。

【绝对禁止 Production Integration】
    全局状态 QUANT_SCORE_V2_ENABLED 默认且永远是 false。
    不能由数据增加 / Validation PROMISING / 自动 workflow / AI / 脚本自动变为 true。
    未来必须人工明确批准（Phase 5 Walk-Forward 之后，另行授权）。

【状态机（严格）】
    RESEARCH → CANDIDATE → APPROVED → PRODUCTION
    本阶段任何模型只能处于 RESEARCH 或 CANDIDATE，绝不 APPROVED / PRODUCTION。

【Evidence Gate（候选资格判定）】
    NOT_ENOUGH_DATA        → BLOCKED
    EXPLORATORY            → BLOCKED
    WEAK_EVIDENCE          → BLOCKED
    INCONCLUSIVE           → BLOCKED
    POTENTIALLY_REDUNDANT  → BLOCKED（默认禁止单独追加）
    PROMISING              → ELIGIBLE（可进 Candidate Model，但权重由后续 Phase 确定）
    REGIME_DEPENDENT       → ELIGIBLE_REGIME_ONLY（只能进入带 Regime 条件的候选）

【无数据时的严格行为】
    Snapshot=0 / Validation 全 NOT_ENOUGH_DATA 时：
    - 所有 Factor：Candidate_Status = BLOCKED
    - 所有 Model：STATUS = NOT_ENOUGH_DATA / DISABLED
    - 绝不输出 Weight=0.20、Expected Return=2.4% 之类的伪造数字。

【数据来源（只读）】
    quant_factor_validation.csv（Phase 3 输出）→ 决定 Evidence_Status
    quant_factor_correlation.csv（Phase 3 输出）→ 决定因子聚类
    绝不读取 Review / Portfolio / Exit / Stop Loss / AI 构造新因子。

【标准化方法（明确记录，供 Phase 5 Walk-Forward 使用）】
    - cross_sectional_percentile：横截面分位（每 Scan 日内 0~100）
    - winsorized_zscore：5%/95% 截尾 z-score
    本阶段只记录方法，不拟合任何历史参数。
"""

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

# ============================================================================
# 全局开关：默认且永远 false（不可自动翻转）
# ============================================================================
QUANT_SCORE_V2_ENABLED = False

REGISTRY_PATH = "quant_factor_registry.csv"
CLUSTERS_PATH = "quant_factor_clusters.csv"
CANDIDATES_PATH = "quant_score_v2_candidates.csv"
CONFIG_PATH = "quant_score_v2_config.json"
REPORT_PATH = "quant_score_v2_report.json"

VALIDATION_PATH = "quant_factor_validation.csv"
CORRELATION_PATH = "quant_factor_correlation.csv"

# 输出 schema 版本（STEP 3-A）：写入 registry/clusters/candidates CSV 与 config/report JSON。
# 命名规则：phase<阶段>.v<主版本>，与 Phase 1–7 完全一致；字段结构变更时递增主版本号。
SCHEMA_VERSION = "phase4.v1"

# ============================================================================
# Factor Registry 静态定义
# ============================================================================
# (Factor, Primary Group, Secondary Group, Direction, Primary Source)
# Direction: POSITIVE / NEGATIVE / NON_MONOTONIC / UNKNOWN
#   - POSITIVE: 因子值越高，未来收益倾向于越高（需 Phase 3 证据确认，此处为"假设方向"）
#   - 无充分证据时一律 UNKNOWN，绝不默认"高分一定好"
FACTOR_REGISTRY_DEF = [
    # Factor, Group, Secondary_Group, Direction, Source
    ("RSI_14",                    "MEAN_REVERSION",    "MOMENTUM",           "UNKNOWN", "scan.py build_stock_pool"),
    ("MACD_Hist",                 "TREND",             "",                   "UNKNOWN", "scan.py build_stock_pool"),
    ("MA20",                      "TREND",             "",                   "UNKNOWN", "scan.py build_stock_pool"),
    ("MA50",                      "TREND",             "",                   "UNKNOWN", "scan.py build_stock_pool"),
    ("MA20_Slope_5D",             "TREND",             "",                   "UNKNOWN", "scan.py build_stock_pool"),
    ("ATR_Pct",                   "VOLATILITY",        "",                   "UNKNOWN", "scan.py build_stock_pool"),
    ("KDJ_J",                     "MOMENTUM",          "MEAN_REVERSION",     "UNKNOWN", "scan.py build_stock_pool"),
    ("Volume_Ratio_5D",           "LIQUIDITY",         "",                   "UNKNOWN", "scan.py build_stock_pool"),
    ("Bias_Pct",                  "TREND",             "MEAN_REVERSION",     "UNKNOWN", "scan.py build_stock_pool"),
    ("Momentum_5D_Pct",           "MOMENTUM",          "",                   "UNKNOWN", "quant_factor_lab.py"),
    ("Momentum_20D_Pct",          "MOMENTUM",          "",                   "UNKNOWN", "quant_factor_lab.py"),
    ("Momentum_60D_Pct",          "MOMENTUM",          "",                   "UNKNOWN", "quant_factor_lab.py"),
    ("Realized_Volatility_20D_Pct", "VOLATILITY",      "",                   "UNKNOWN", "quant_factor_lab.py"),
    ("Volume_Ratio_20D",          "LIQUIDITY",         "",                   "UNKNOWN", "quant_factor_lab.py"),
    ("ZScore_20D",                "MEAN_REVERSION",    "",                   "UNKNOWN", "quant_factor_lab.py"),
    ("Beta_60D_SPY",              "RELATIVE_STRENGTH", "MARKET_REGIME",      "UNKNOWN", "quant_factor_lab.py"),
    ("Stock_RS_20D_vs_SPY",       "RELATIVE_STRENGTH", "",                   "UNKNOWN", "quant_factor_lab.py"),
    ("Sector_RS_20D_Pct",         "RELATIVE_STRENGTH", "",                   "UNKNOWN", "scan.py market_context"),
    ("VIX",                       "MARKET_REGIME",     "VOLATILITY",         "UNKNOWN", "scan.py market_context"),
    ("Fundamental_Score",         "FUNDAMENTAL",       "",                   "UNKNOWN", "scan.py score_candidate_quality"),
    ("Event_Score",               "EVENT",             "",                   "UNKNOWN", "scan.py score_candidate_quality"),
    ("Technical_Score_25",        "TREND",             "MOMENTUM",           "UNKNOWN", "scan.py score_candidate_quality"),
    ("Risk_Liquidity_Score",      "LIQUIDITY",         "VOLATILITY",         "UNKNOWN", "scan.py score_candidate_quality"),
    ("Quant_Score",               "FUNDAMENTAL",       "",                   "UNKNOWN", "scan.py score_candidate_quality (EXISTING)"),
]

GROUPS = [
    "TREND", "MOMENTUM", "MEAN_REVERSION", "VOLATILITY", "LIQUIDITY",
    "RELATIVE_STRENGTH", "MARKET_REGIME", "FUNDAMENTAL", "EVENT",
]

NORMALIZATION_METHODS = ["cross_sectional_percentile", "winsorized_zscore"]

# 候选模型定义（架构占位，权重待 Phase 5 经 Walk-Forward 后由人工批准）
CANDIDATE_MODELS = {
    "MODEL_A_CONSERVATIVE": {
        "description": "保守：TREND + FUNDAMENTAL + LIQUIDITY，低动量暴露",
        "group_weights": {"TREND": 0.4, "FUNDAMENTAL": 0.3, "LIQUIDITY": 0.2, "MARKET_REGIME": 0.1},
    },
    "MODEL_B_BALANCED": {
        "description": "均衡：各 Group 接近等权",
        "group_weights": {"TREND": 0.25, "MOMENTUM": 0.15, "MEAN_REVERSION": 0.15,
                          "VOLATILITY": 0.1, "LIQUIDITY": 0.1, "RELATIVE_STRENGTH": 0.15,
                          "MARKET_REGIME": 0.1},
    },
    "MODEL_C_MOMENTUM": {
        "description": "动量：MOMENTUM + RELATIVE_STRENGTH 为主",
        "group_weights": {"MOMENTUM": 0.4, "RELATIVE_STRENGTH": 0.3, "TREND": 0.2, "LIQUIDITY": 0.1},
    },
}

# Evidence → Candidate 资格映射
EVIDENCE_GATE = {
    "NOT_ENOUGH_DATA": "BLOCKED",
    "EXPLORATORY": "BLOCKED",
    "WEAK_EVIDENCE": "BLOCKED",
    "INCONCLUSIVE": "BLOCKED",
    "POTENTIALLY_REDUNDANT": "BLOCKED",
    "PROMISING": "ELIGIBLE",
    "REGIME_DEPENDENT": "ELIGIBLE_REGIME_ONLY",
}


# ============================================================================
# 1. Factor Registry
# ============================================================================
def build_factor_registry(validation_df=None):
    """构建 Factor Registry，融合 Phase 3 Evidence_Status。返回 DataFrame。

    validation_df: quant_factor_validation.csv 内容（可选；空则 Evidence_Status=NOT_ENOUGH_DATA）。
    """
    rows = []
    evidence_map = {}
    if validation_df is not None and not validation_df.empty:
        if "Factor" in validation_df.columns and "Status" in validation_df.columns:
            # 一个 Factor 有 3 个 Horizon 行，取"最有利"的状态作为该因子证据
            for factor, g in validation_df.groupby("Factor"):
                statuses = g["Status"].tolist()
                evidence_map[factor] = _best_evidence(statuses)
    for factor, group, secondary, direction, source in FACTOR_REGISTRY_DEF:
        ev = evidence_map.get(factor, "NOT_ENOUGH_DATA")
        rows.append({
            "Factor": factor,
            "Group": group,
            "Secondary_Group": secondary,
            "Direction": direction,
            "Evidence_Status": ev,
            "Enabled": "true" if ev == "PROMISING" else "false",
            "Primary_Source": source,
        })
    return pd.DataFrame(rows)


def _best_evidence(statuses):
    """取一组 Status 中"最有利"的一个（用于 Factor 级证据聚合）。"""
    rank = {
        "NOT_ENOUGH_DATA": 0, "EXPLORATORY": 1, "WEAK_EVIDENCE": 2,
        "INCONCLUSIVE": 3, "POTENTIALLY_REDUNDANT": 4,
        "REGIME_DEPENDENT": 5, "PROMISING": 6,
    }
    return max(statuses, key=lambda s: rank.get(s, 0))


def candidate_status(evidence_status):
    """Evidence → Candidate 资格（Evidence Gate）。"""
    return EVIDENCE_GATE.get(evidence_status, "BLOCKED")


# ============================================================================
# 2. Factor Cluster（冗余聚类，只建候选机制，不自动删除）
# ============================================================================
def build_factor_clusters(correlation_df, threshold=0.9):
    """由因子相关矩阵建立冗余聚类。返回 DataFrame。

    只标记 POTENTIALLY_REDUNDANT 的因子对所属 Cluster，不自动删除、不改权重。
    """
    if correlation_df is None or correlation_df.empty:
        return pd.DataFrame(columns=["Cluster", "Factor_A", "Factor_B", "Pearson", "Spearman"])

    rows = []
    cluster_id = 0
    seen = set()
    for _, r in correlation_df.iterrows():
        fa = str(r.get("Factor_A", ""))
        fb = str(r.get("Factor_B", ""))
        pearson = _to_float(r.get("Pearson"))
        spearman = _to_float(r.get("Spearman"))
        red = False
        if pearson is not None and abs(pearson) >= threshold:
            red = True
        if spearman is not None and abs(spearman) >= threshold:
            red = True
        if not red:
            continue
        key = tuple(sorted([fa, fb]))
        if key in seen:
            continue
        seen.add(key)
        cluster_id += 1
        rows.append({
            "Cluster": f"Cluster_{cluster_id:03d}",
            "Factor_A": fa,
            "Factor_B": fb,
            "Pearson": pearson,
            "Spearman": spearman,
        })
    return pd.DataFrame(rows)


# ============================================================================
# 3. Candidate Models
# ============================================================================
def build_candidate_models(registry_df):
    """由 Registry 生成候选模型因子清单。返回 DataFrame。

    无足够证据时，所有 Factor 的 Candidate_Status = BLOCKED，Weight = None。
    """
    if registry_df is None or registry_df.empty:
        return pd.DataFrame(columns=["Model", "Factor", "Group", "Weight", "Evidence_Status", "Candidate_Status"])

    rows = []
    for model, spec in CANDIDATE_MODELS.items():
        gw = spec["group_weights"]
        for _, r in registry_df.iterrows():
            factor = r["Factor"]
            group = r["Group"]
            ev = r["Evidence_Status"]
            cs = candidate_status(ev)
            rows.append({
                "Model": model,
                "Factor": factor,
                "Group": group,
                "Weight": None,  # 权重由 Phase 5 Walk-Forward 后人工批准，本阶段不给伪造权重
                "Evidence_Status": ev,
                "Candidate_Status": cs,
            })
    return pd.DataFrame(rows)


def model_statuses(registry_df):
    """计算每个候选模型的整体状态。

    返回 {model: status}，status ∈ NOT_ENOUGH_DATA / DISABLED / CANDIDATE。
    无任何 PROMISING 证据 → 所有 model 保持 NOT_ENOUGH_DATA / DISABLED。
    """
    statuses = {}
    if registry_df is None or registry_df.empty:
        return {m: "NOT_ENOUGH_DATA" for m in CANDIDATE_MODELS}
    has_promising = (registry_df["Evidence_Status"] == "PROMISING").any()
    has_regime_dep = (registry_df["Evidence_Status"] == "REGIME_DEPENDENT").any()
    for model in CANDIDATE_MODELS:
        if not has_promising and not has_regime_dep:
            statuses[model] = "NOT_ENOUGH_DATA"
        elif has_regime_dep and not has_promising:
            statuses[model] = "DISABLED"
        else:
            statuses[model] = "CANDIDATE"
    return statuses


# ============================================================================
# 4. Config / Report
# ============================================================================
def build_config(model_statuses):
    """构造 config JSON dict。QUANT_SCORE_V2_ENABLED 恒为 False。"""
    return {
        "schema_version": SCHEMA_VERSION,
        "QUANT_SCORE_V2_ENABLED": bool(QUANT_SCORE_V2_ENABLED),  # 恒 False
        "enable_note": "Phase 4 研究框架，默认且永远关闭；仅当 Phase 5 Walk-Forward 验证通过并经人工批准后才可开启。",
        "models": {m: {"status": s, "group_weights": CANDIDATE_MODELS[m]["group_weights"],
                       "description": CANDIDATE_MODELS[m]["description"]}
                   for m, s in model_statuses.items()},
        "factor_groups": GROUPS,
        "normalization": {
            "methods": NORMALIZATION_METHODS,
            "selected": "cross_sectional_percentile",
            "note": "标准化参数不拟合历史全样本；为 Phase 5 Walk-Forward 预留接口。",
        },
        "eligibility_rules": {
            "evidence_gate": EVIDENCE_GATE,
            "redundancy_threshold": 0.9,
            "note": "PROMISING ≠ APPROVED；候选因子需经 Phase 5 OOS 验证后才可进入生产。",
        },
        "state_machine": ["RESEARCH", "CANDIDATE", "APPROVED", "PRODUCTION"],
    }


def build_report(registry_df, cluster_df, candidates_df, model_statuses):
    """构造 report JSON dict。"""
    n_promising = int((registry_df["Evidence_Status"] == "PROMISING").sum()) if registry_df is not None and not registry_df.empty else 0
    n_regime = int((registry_df["Evidence_Status"] == "REGIME_DEPENDENT").sum()) if registry_df is not None and not registry_df.empty else 0
    n_blocked = int((candidates_df["Candidate_Status"] == "BLOCKED").sum()) if candidates_df is not None and not candidates_df.empty else 0
    n_eligible = int((candidates_df["Candidate_Status"] == "ELIGIBLE").sum()) if candidates_df is not None and not candidates_df.empty else 0
    return {
        "schema_version": SCHEMA_VERSION,
        "QUANT_SCORE_V2_ENABLED": bool(QUANT_SCORE_V2_ENABLED),
        "state": "RESEARCH",
        "candidate_model_statuses": model_statuses,
        "evidence_summary": {
            "n_factors": len(registry_df) if registry_df is not None else 0,
            "n_promising": n_promising,
            "n_regime_dependent": n_regime,
        },
        "eligibility_summary": {
            "n_blocked": n_blocked,
            "n_eligible": n_eligible,
        },
        "redundant_clusters": int(len(cluster_df)) if cluster_df is not None else 0,
        "no_decision_rule": "Phase 4 只产出候选研究框架；任何模型不得 APPROVED/PRODUCTION，"
                            "不得自动启用，权重待 Phase 5 Walk-Forward 后人工批准。",
    }


# ============================================================================
# 5. 主入口
# ============================================================================
def _to_float(v):
    try:
        f = float(v)
        if np.isnan(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def load_csv(path):
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str, keep_default_na=False)
    except Exception:
        return pd.DataFrame()


def run_quant_score_v2(validation_path=VALIDATION_PATH, correlation_path=CORRELATION_PATH,
                       registry_path=REGISTRY_PATH, clusters_path=CLUSTERS_PATH,
                       candidates_path=CANDIDATES_PATH, config_path=CONFIG_PATH, report_path=REPORT_PATH):
    """读 Phase 3 输出 → 构建 registry / clusters / candidates / config / report。返回状态 dict。"""
    result = {
        "validation_rows": 0,
        "status": "NOT_ENOUGH_DATA",
        "registry_rows": 0,
        "cluster_rows": 0,
        "candidate_rows": 0,
        "n_promising": 0,
        # R1 修复：是否真的写出了产物。无数据时保持 False，绝不出文件。
        "written": False,
    }

    # R1 防呆修复（STEP 3-C）：Phase 3 无真实验证结果 → 不构建、不落盘。
    # 旧行为会用全 NOT_ENOUGH_DATA 写出 5 份文件，下游看到"文件存在"会误以为
    # Phase 4 已产出候选模型。改为只返回状态与缺口原因。
    if not os.path.exists(validation_path):
        result["reason"] = f"validation 不存在：{validation_path}（Phase 3 尚无真实结果）"
        return result

    validation_df = load_csv(validation_path)
    correlation_df = load_csv(correlation_path)
    result["validation_rows"] = int(len(validation_df))
    if validation_df.empty:
        result["reason"] = "validation 为空（Phase 3 尚无真实验证结果，绝不做历史回填）"
        return result

    registry_df = build_factor_registry(validation_df)
    cluster_df = build_factor_clusters(correlation_df)
    candidates_df = build_candidate_models(registry_df)
    model_states = model_statuses(registry_df)

    result["registry_rows"] = int(len(registry_df))
    result["cluster_rows"] = int(len(cluster_df))
    result["candidate_rows"] = int(len(candidates_df))
    result["n_promising"] = int((registry_df["Evidence_Status"] == "PROMISING").sum())

    # 原子写
    for _df in (registry_df, cluster_df, candidates_df):
        if _df is not None:
            _df["schema_version"] = SCHEMA_VERSION
    registry_df.to_csv(registry_path, index=False, encoding="utf-8")
    cluster_df.to_csv(clusters_path, index=False, encoding="utf-8")
    candidates_df.to_csv(candidates_path, index=False, encoding="utf-8")

    config = build_config(model_states)
    tmp = config_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    os.replace(tmp, config_path)

    report = build_report(registry_df, cluster_df, candidates_df, model_states)
    tmp = report_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    os.replace(tmp, report_path)

    result["status"] = "OK"
    result["written"] = True
    return result


def main(argv=None):
    """命令行入口（STEP 3-C）：与 Phase 2 一致的退出码语义。

    退出码：0 = OK，或数据不足（预期状态）；1 = --strict 下数据不足。
    注：旧实现把"非 OK 一律返回 1"，本步骤改为与其余 Phase 一致
    （数据不足默认不算失败，避免阻断 workflow），需要强告警时用 --strict。
    """
    ap = argparse.ArgumentParser(description="Quant Phase 4 · Quant Score V2（研究候选，V2 恒 DISABLED）")
    ap.add_argument("--validation", default=VALIDATION_PATH, help=f"Phase 3 验证 CSV（默认 {VALIDATION_PATH}）")
    ap.add_argument("--correlation", default=CORRELATION_PATH, help=f"Phase 3 相关矩阵 CSV（默认 {CORRELATION_PATH}）")
    ap.add_argument("--registry", default=REGISTRY_PATH, help=f"registry 输出（默认 {REGISTRY_PATH}）")
    ap.add_argument("--clusters", default=CLUSTERS_PATH, help=f"clusters 输出（默认 {CLUSTERS_PATH}）")
    ap.add_argument("--candidates", default=CANDIDATES_PATH, help=f"candidates 输出（默认 {CANDIDATES_PATH}）")
    ap.add_argument("--config", default=CONFIG_PATH, help=f"config 输出（默认 {CONFIG_PATH}）")
    ap.add_argument("--report", default=REPORT_PATH, help=f"report 输出（默认 {REPORT_PATH}）")
    ap.add_argument("--strict", action="store_true", help="数据不足时以退出码 1 退出（默认 0）")
    args = ap.parse_args(argv)

    r = run_quant_score_v2(validation_path=args.validation, correlation_path=args.correlation,
                           registry_path=args.registry, clusters_path=args.clusters,
                           candidates_path=args.candidates, config_path=args.config,
                           report_path=args.report)
    print("[Quant Score V2]", r)
    if r["status"] == "OK":
        return 0
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
