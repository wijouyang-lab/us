# -*- coding: utf-8 -*-
"""
Quant Score V2 Shadow Mode —— 阶段 6：影子观察框架（纯研究层，非交易层）。

【定位】
    让 CURRENT_EXISTING_QUANT_SCORE 与 QUANT SCORE V2 CANDIDATE 在同一候选池上并行运行，
    但 V2 只能 OBSERVE_ONLY，绝不改变 Scan 推荐 / Core-Observation / Final Score /
    Stop Loss / AI Prompt / Review / Portfolio。

【Production Isolation】
    QUANT_SCORE_V2_ENABLED 恒 false（继承 Phase 4/5），Phase 6 永不修改。
    禁止 AUTO_PROMOTE / AUTO_REPLACE / AUTO_WEIGHT_UPDATE。

【Shadow Governance】
    SHADOW_DISABLED（默认）/ SHADOW_ACTIVE / SHADOW_PAUSED
    SHADOW_ENABLE = false（默认），SHADOW_START_DATE = null。
    不能因代码部署自动变 ACTIVE，必须人工明确启用。

【历史连续性】
    Shadow 从正式启用后的第一天开始，绝不把过去 Scan 历史回填构造成 Shadow。

【数据流（同一候选池）】
    Scan Candidate Pool → Existing Quant Score → Existing Recommendation
    同一 Candidate Pool → Quant Score V2 Candidate → Shadow Recommendation
    两条路径必须同一批股票 / 同一 Scan_Date / 同一基础市场数据。

【Selection Bias 正确性】
    必须同时保存 3 个视角：Entire Candidate Pool / Shadow Selected / Existing Selected。
    Incremental Value = Shadow Only vs Existing Only（未来收益对比）。

【AI / 网络】
    AI Calls = 0；网络请求 = 0；Shadow Score 纯确定性计算；只读已持久化研究数据。

【严格空数据行为】
    Snapshot=0 → Shadow Status = NOT_ENOUGH_DATA；Selection Count = None（无运行记录，非失败）；
    5D/10D/20D = NOT_ENOUGH_DATA；Performance = None。绝不输出 Win_Rate=0% / Return=0%。
"""

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
# Forward Return 唯一真源：统一复用 Phase 2 的 forward_return_nd，绝不另起一套口径。
from quant_factor_backtest import forward_return_nd

SNAPSHOT_PATH = "quant_factor_snapshot.csv"
PERFORMANCE_PATH = "quant_shadow_performance.csv"
REPORT_PATH = "quant_shadow_report.json"
SHADOW_SNAPSHOT_PATH = "quant_shadow_snapshot.csv"

# ============================================================================
# Governance 全局状态（默认禁用，绝不自动激活）
# ============================================================================
SHADOW_ENABLE = False
SHADOW_START_DATE = None  # 正式启用日期（YYYY-MM-DD），需人工设置

HORIZONS = (5, 10, 20)
BENCHMARK_MODEL = "CURRENT_EXISTING_QUANT_SCORE"

# 输出 schema 版本（STEP 3-A）：写入 shadow snapshot/performance CSV 与 report.json。
# 命名规则：phase<阶段>.v<主版本>，与 Phase 1–7 完全一致；字段结构变更时递增主版本号。
SCHEMA_VERSION = "phase6.v1"

# factor -> primary group（来自 Phase 4，不重定义）
FACTOR_GROUP = {f: g for f, g, sg, d, src in FACTOR_REGISTRY_DEF}
RAW_FACTORS = [f for f, g, sg, d, src in FACTOR_REGISTRY_DEF if f != "Quant_Score"]

# Existing 视为"已选中"的 Tag
EXISTING_SELECTED_TAGS = {"Core_Dragon", "Observation"}


def _to_float(v):
    try:
        f = float(v)
        if np.isnan(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


# ============================================================================
# 1. Shadow 评分（纯确定性，横截面 percentile，无未来数据）
# ============================================================================
def compute_shadow_score(day_df, model_name):
    """在单个 Scan_Date 的横截面上计算 Shadow Score（纯确定性）。

    对每个因子做横截面 percentile（0~100），按 Phase 4 group 权重加权。
    缺失因子按中性（0）处理，绝不外推未来数据。
    """
    if day_df is None or day_df.empty:
        return pd.Series(dtype=float)
    gw = CANDIDATE_MODELS[model_name]["group_weights"]
    # 计算每个因子的横截面 percentile rank（0~100）
    pct = {}
    for f in RAW_FACTORS:
        if f not in day_df.columns:
            continue
        vals = pd.to_numeric(day_df[f], errors="coerce")
        pct[f] = vals.rank(pct=True) * 100.0
    if not pct:
        return pd.Series(np.nan, index=day_df.index)

    group_factors = {}
    for f in RAW_FACTORS:
        if f in pct:
            group_factors.setdefault(FACTOR_GROUP.get(f, "OTHER"), []).append(f)

    total_w = 0.0
    score = pd.Series(0.0, index=day_df.index)
    for g, w in gw.items():
        if g not in group_factors:
            continue
        cols = group_factors[g]
        # group 内因子等权平均（缺失按中性 0）
        gscore = pd.concat([pct[c] for c in cols], axis=1).fillna(0.0).mean(axis=1)
        score += w * gscore
        total_w += w
    if total_w > 0:
        score = score / total_w
    return score


def shadow_rank(day_df, model_name):
    """返回该 Scan_Date 横截面内 Shadow Rank（1 为最高分）。"""
    score = compute_shadow_score(day_df, model_name)
    return score.rank(ascending=False, method="first")


# ============================================================================
# 2. Difference_Type 分类
# ============================================================================
def classify_difference(existing_selected, shadow_selected):
    """由两个布尔标志判定 Difference_Type。返回 BOTH_SELECTED / EXISTING_ONLY / SHADOW_ONLY / BOTH_REJECTED。"""
    if existing_selected and shadow_selected:
        return "BOTH_SELECTED"
    if existing_selected and not shadow_selected:
        return "EXISTING_ONLY"
    if not existing_selected and shadow_selected:
        return "SHADOW_ONLY"
    return "BOTH_REJECTED"


# ============================================================================
# 3. Shadow Snapshot（全候选池）
# ============================================================================
def build_shadow_snapshot(snapshot_df, shadow_model, top_k=5):
    """由 Factor Snapshot 生成 Shadow Snapshot（记录全候选池 + Difference_Type）。

    snapshot_df: quant_factor_snapshot.csv（含 Scan_Date, Ticker, Quant_Score, Tag?）。
    existing selected 判定：Tag ∈ {Core_Dragon, Observation}（若无 Tag 列则按 Quant_Score 前 top_k）。
    """
    if snapshot_df is None or snapshot_df.empty:
        return pd.DataFrame()

    rows = []
    for scan_date, day in snapshot_df.groupby("Scan_Date"):
        day = day.copy()
        rank = shadow_rank(day, shadow_model)
        # Existing selected：优先用 Tag，否则用 Quant_Score 前 top_k
        if "Tag" in day.columns:
            existing_sel = pd.Series(day["Tag"].astype(str).isin(EXISTING_SELECTED_TAGS).values,
                                     index=day.index)
        else:
            q = pd.to_numeric(day.get("Quant_Score"), errors="coerce")
            top_q = q.nlargest(top_k).index if q.notna().any() else pd.Index([])
            existing_sel = pd.Series(day.index.isin(top_q), index=day.index)

        shadow_top = rank.nsmallest(top_k).index
        shadow_sel = pd.Series(day.index.isin(shadow_top), index=day.index)

        for idx, r in day.iterrows():
            es = bool(existing_sel.loc[idx])
            ss = bool(shadow_sel.loc[idx])
            rows.append({
                "Scan_Date": str(scan_date),
                "Ticker": str(r.get("Ticker", "") or ""),
                "Name": str(r.get("Name", "") or ""),
                "Sector": str(r.get("Sector", "") or ""),
                "Existing_Quant_Score": r.get("Quant_Score", ""),
                "Existing_Final_Score": r.get("Final_Score", "") if "Final_Score" in day.columns else "",
                "Existing_Tag": r.get("Tag", "") if "Tag" in day.columns else "",
                "Shadow_Model": shadow_model,
                "Shadow_Score": round(float(compute_shadow_score(day, shadow_model).loc[idx]), 4) if idx in day.index else "",
                "Shadow_Rank": int(rank.loc[idx]) if idx in rank.index else "",
                "Existing_Selected": "true" if es else "false",
                "Shadow_Selected": "true" if ss else "false",
                "Difference_Type": classify_difference(es, ss),
                "Market_Regime": str(r.get("Market_Regime", "") or ""),
                "VIX": r.get("VIX", ""),
                "Price": r.get("Price", ""),
            })
    return pd.DataFrame(rows)


# ============================================================================
# 4. Performance Tracking（真实 Forward Return，缺价 → None）
# ============================================================================
def build_shadow_performance(snapshot_df, price_map):
    """对全候选池每个 ticker 计算 5D/10D/20D forward return，返回长表。缺价 → None。

    Forward Return 统一调用 quant_factor_backtest.forward_return_nd（唯一真源），
    与 Backtest 完全同口径，杜绝同名函数不同公式的历史污染。
    """
    if snapshot_df is None or snapshot_df.empty:
        return pd.DataFrame()
    rows = []
    for _, r in snapshot_df.iterrows():
        ticker = str(r.get("Ticker", "") or "").strip()
        tech = str(r.get("Technical_Date", "") or "").strip()
        close_t = _to_float(r.get("Price"))
        series = price_map.get(ticker) if price_map else None
        row = {"Scan_Date": r.get("Scan_Date", ""), "Ticker": ticker}
        for n in HORIZONS:
            fr = forward_return_nd(series, tech, close_t, n)
            row[f"Forward_Return_{n}D"] = fr
        rows.append(row)
    return pd.DataFrame(rows)


def performance_summary(perf_df):
    """由 performance 长表聚合统计。缺价样本不进入分母。返回 dict。"""
    out = {}
    for n in HORIZONS:
        col = f"Forward_Return_{n}D"
        r = pd.to_numeric(perf_df[col], errors="coerce").dropna() if perf_df is not None and not perf_df.empty else pd.Series(dtype=float)
        if r.empty:
            out[f"{n}D"] = {"status": "NOT_ENOUGH_DATA", "N": 0, "Win_Rate": None,
                            "Average_Return": None, "Median_Return": None}
            continue
        pos = int((r > 0).sum())
        out[f"{n}D"] = {
            "status": "OK" if len(r) >= 30 else "NOT_ENOUGH_DATA",
            "N": int(len(r)),
            "Win_Rate": round(float(pos / len(r) * 100), 2),
            "Average_Return": round(float(r.mean()), 6),
            "Median_Return": round(float(r.median()), 6),
        }
    return out


# ============================================================================
# 5. Report
# ============================================================================
def build_report(shadow_status, start_date, snapshot_df, shadow_snapshot_df, perf_df,
                 model_names):
    """构造 report JSON dict。"""
    existing_count = None
    shadow_count = None
    overlap = None
    if shadow_snapshot_df is not None and not shadow_snapshot_df.empty:
        existing_count = int((shadow_snapshot_df["Existing_Selected"] == "true").sum())
        shadow_count = int((shadow_snapshot_df["Shadow_Selected"] == "true").sum())
        both = int((shadow_snapshot_df["Difference_Type"] == "BOTH_SELECTED").sum())
        overlap = round(float(both / existing_count * 100), 2) if existing_count else None

    diff_counts = {}
    if shadow_snapshot_df is not None and not shadow_snapshot_df.empty:
        diff_counts = shadow_snapshot_df["Difference_Type"].value_counts().to_dict()

    return {
        "schema_version": SCHEMA_VERSION,
        "shadow_status": shadow_status,
        "shadow_start_date": start_date,
        "current_data_maturity": {
            "snapshot_rows": int(len(snapshot_df)) if snapshot_df is not None else 0,
            "shadow_snapshot_rows": int(len(shadow_snapshot_df)) if shadow_snapshot_df is not None else 0,
        },
        "candidate_models": model_names,
        "existing_selection_count": existing_count,
        "shadow_selection_count": shadow_count,
        "overlap_rate": overlap,
        "difference_type_counts": diff_counts,
        "5D_status": performance_summary(perf_df).get("5D", {}).get("status"),
        "10D_status": performance_summary(perf_df).get("10D", {}).get("status"),
        "20D_status": performance_summary(perf_df).get("20D", {}).get("status"),
        "existing_performance": None,   # 数据成熟后按 Existing Selected 分组统计
        "shadow_performance": None,
        "shadow_only_performance": None,
        "existing_only_performance": None,
        "regime_summary": {},
        "stability_summary": {},
        "insufficient_data_reasons": _insufficient_reasons(shadow_status, snapshot_df),
        "production_lock": {
            "QUANT_SCORE_V2_ENABLED": bool(QUANT_SCORE_V2_ENABLED),
            "SHADOW_ENABLE": bool(SHADOW_ENABLE),
            "note": "Shadow 只能 OBSERVE_ONLY；禁止 AUTO_PROMOTE/AUTO_REPLACE/AUTO_WEIGHT_UPDATE。",
        },
    }


def _insufficient_reasons(shadow_status, snapshot_df):
    reasons = []
    if shadow_status == "SHADOW_DISABLED":
        reasons.append("SHADOW_ENABLE=false，未人工启用")
    if snapshot_df is None or snapshot_df.empty:
        reasons.append("Snapshot=0，无候选池数据")
    return reasons


# ============================================================================
# 6. 主入口
# ============================================================================
def load_csv(path):
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str, keep_default_na=False)
    except Exception:
        return pd.DataFrame()


def run_shadow(snapshot_path=SNAPSHOT_PATH, price_map=None,
               shadow_model="MODEL_B_BALANCED", top_k=5,
               shadow_snapshot_path=SHADOW_SNAPSHOT_PATH,
               performance_path=PERFORMANCE_PATH, report_path=REPORT_PATH):
    """读 snapshot → 计算 shadow 快照/performance → 写三份输出。返回状态 dict。"""
    model_names = list(CANDIDATE_MODELS.keys()) + [BENCHMARK_MODEL]
    result = {
        "snapshot_rows": 0,
        "shadow_status": "SHADOW_DISABLED",
        "status": "NOT_ENOUGH_DATA",
        "shadow_snapshot_rows": 0,
        "performance_rows": 0,
    }

    # Governance：未启用 → 不产生 shadow，输出禁用状态
    if not SHADOW_ENABLE:
        result["reason"] = "SHADOW_ENABLE=false（未人工启用），Shadow 保持 DISABLED"
        snapshot_df = load_csv(snapshot_path)
        result["snapshot_rows"] = int(len(snapshot_df))
        _write_disabled_outputs(shadow_snapshot_path, performance_path, report_path,
                                result, snapshot_df, model_names)
        return result

    # 已启用：需要 SHADOW_START_DATE
    start_date = SHADOW_START_DATE
    if not start_date:
        result["reason"] = "SHADOW_ENABLE=true 但 SHADOW_START_DATE=null，无法确定启用日"
        snapshot_df = load_csv(snapshot_path)
        result["snapshot_rows"] = int(len(snapshot_df))
        _write_disabled_outputs(shadow_snapshot_path, performance_path, report_path,
                                result, snapshot_df, model_names)
        return result

    snapshot_df = load_csv(snapshot_path)
    result["snapshot_rows"] = int(len(snapshot_df))
    result["shadow_status"] = "SHADOW_ACTIVE"
    if snapshot_df.empty:
        result["status"] = "NOT_ENOUGH_DATA"
        result["reason"] = "Snapshot=0（无候选池数据）"
        _write_disabled_outputs(shadow_snapshot_path, performance_path, report_path,
                                result, snapshot_df, model_names)
        return result

    # 只处理 start_date 之后（含）的 snapshot（历史连续性，绝不回填）
    if "Scan_Date" in snapshot_df.columns:
        mask = snapshot_df["Scan_Date"].astype(str) >= str(start_date)
        snapshot_df = snapshot_df[mask]

    shadow_snap = build_shadow_snapshot(snapshot_df, shadow_model, top_k)
    perf = build_shadow_performance(snapshot_df, price_map)

    shadow_snap["schema_version"] = SCHEMA_VERSION
    perf["schema_version"] = SCHEMA_VERSION
    shadow_snap.to_csv(shadow_snapshot_path, index=False, encoding="utf-8")
    perf.to_csv(performance_path, index=False, encoding="utf-8")

    result["shadow_snapshot_rows"] = int(len(shadow_snap))
    result["performance_rows"] = int(len(perf))

    report = build_report("SHADOW_ACTIVE", str(start_date), snapshot_df, shadow_snap, perf, model_names)
    tmp = report_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    os.replace(tmp, report_path)

    result["status"] = "OK"
    return result


def _write_disabled_outputs(shadow_snapshot_path, performance_path, report_path, result, snapshot_df, model_names):
    if shadow_snapshot_path:
        pd.DataFrame(columns=[
            "Scan_Date", "Ticker", "Name", "Sector", "Existing_Quant_Score",
            "Existing_Final_Score", "Existing_Tag", "Shadow_Model", "Shadow_Score", "Shadow_Rank",
            "Existing_Selected", "Shadow_Selected", "Difference_Type", "Market_Regime", "VIX", "Price",
        ]).to_csv(shadow_snapshot_path, index=False, encoding="utf-8")
    if performance_path:
        pd.DataFrame(columns=["Scan_Date", "Ticker", "Forward_Return_5D", "Forward_Return_10D", "Forward_Return_20D"]).to_csv(
            performance_path, index=False, encoding="utf-8")
    if report_path:
        report = build_report("SHADOW_DISABLED", SHADOW_START_DATE, snapshot_df,
                              pd.DataFrame(), pd.DataFrame(), model_names)
        tmp = report_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        os.replace(tmp, report_path)


def main(argv=None):
    r = run_shadow()
    print("[Shadow]", r)
    return 0 if r["status"] in ("OK", "NOT_ENOUGH_DATA") else 1


if __name__ == "__main__":
    sys.exit(main())
