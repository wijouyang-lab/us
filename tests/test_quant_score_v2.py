# -*- coding: utf-8 -*-
"""Quant Score 2.0 框架纯函数回归测试（不依赖真实数据/网络）。"""
import json
import os
import sys
import tempfile

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_score_v2 import (
    CANDIDATE_MODELS,
    FACTOR_REGISTRY_DEF,
    QUANT_SCORE_V2_ENABLED,
    build_candidate_models,
    build_config,
    build_factor_clusters,
    build_factor_registry,
    build_report,
    candidate_status,
    model_statuses,
    run_quant_score_v2,
)



def check(name, cond, detail=""):
    """断言：FAIL 时抛出 AssertionError（pytest 可捕获），同时保留打印。"""
    if cond:
        print(f"  [PASS] {name}")
        return True
    print(f"  [FAIL] {name}  {detail}")
    raise AssertionError(f"{name}  {detail}".strip())


def make_validation(statuses):
    """构造 validation 数据：{factor: status}，每个 factor 3 个 horizon 都设同一 status。"""
    rows = []
    for factor, st in statuses.items():
        for h in ["5D", "10D", "20D"]:
            rows.append({"Factor": factor, "Horizon": h, "Status": st, "N": "0"})
    return pd.DataFrame(rows)


# ---- 1-2. 空 validation / NOT_ENOUGH_DATA ----
def test_empty_validation():
    r = build_factor_registry(None)
    check("空 validation → registry 有 24 因子", len(r) == 24, f"got {len(r)}")
    check("全部 Evidence=NOT_ENOUGH_DATA", (r["Evidence_Status"] == "NOT_ENOUGH_DATA").all())
    check("全部 Enabled=false", (r["Enabled"] == "false").all())
    cs = candidate_status("NOT_ENOUGH_DATA")
    check("NOT_ENOUGH_DATA → BLOCKED", cs == "BLOCKED", f"got {cs}")


# ---- 3-7. 各 Evidence 状态的 candidate 资格 ----
def test_evidence_gate():
    check("EXPLORATORY → BLOCKED", candidate_status("EXPLORATORY") == "BLOCKED")
    check("WEAK_EVIDENCE → BLOCKED", candidate_status("WEAK_EVIDENCE") == "BLOCKED")
    check("INCONCLUSIVE → BLOCKED", candidate_status("INCONCLUSIVE") == "BLOCKED")
    check("POTENTIALLY_REDUNDANT → BLOCKED", candidate_status("POTENTIALLY_REDUNDANT") == "BLOCKED")
    check("PROMISING → ELIGIBLE", candidate_status("PROMISING") == "ELIGIBLE")
    check("REGIME_DEPENDENT → ELIGIBLE_REGIME_ONLY", candidate_status("REGIME_DEPENDENT") == "ELIGIBLE_REGIME_ONLY")
    check("未知状态 → BLOCKED", candidate_status("SOMETHING_ELSE") == "BLOCKED")


# ---- 8-9. Candidate blocking / eligibility ----
def test_candidate_blocking_and_eligibility():
    # 全 NOT_ENOUGH_DATA → 全 BLOCKED
    reg = build_factor_registry(None)
    cands = build_candidate_models(reg)
    check("全 BLOCKED", (cands["Candidate_Status"] == "BLOCKED").all())
    check("Weight 全 None（不伪造权重）", cands["Weight"].isna().all())

    # 有一个 PROMISING → 该因子 ELIGIBLE
    val = make_validation({"Momentum_20D_Pct": "PROMISING"})
    reg2 = build_factor_registry(val)
    m20 = reg2[reg2["Factor"] == "Momentum_20D_Pct"].iloc[0]
    check("PROMISING 因子 Evidence=PROMISING", m20["Evidence_Status"] == "PROMISING")
    check("PROMISING 因子 Enabled=true", m20["Enabled"] == "true")
    cands2 = build_candidate_models(reg2)
    m20_c = cands2[(cands2["Factor"] == "Momentum_20D_Pct") & (cands2["Model"] == "MODEL_B_BALANCED")].iloc[0]
    check("PROMISING 因子 → ELIGIBLE", m20_c["Candidate_Status"] == "ELIGIBLE")


# ---- 10-11. Factor registry / grouping ----
def test_registry_grouping():
    reg = build_factor_registry(None)
    check("RSI_14 → MEAN_REVERSION", reg[reg["Factor"] == "RSI_14"]["Group"].iloc[0] == "MEAN_REVERSION")
    check("Momentum_20D → MOMENTUM", reg[reg["Factor"] == "Momentum_20D_Pct"]["Group"].iloc[0] == "MOMENTUM")
    check("ATR_Pct → VOLATILITY", reg[reg["Factor"] == "ATR_Pct"]["Group"].iloc[0] == "VOLATILITY")
    check("Beta → RELATIVE_STRENGTH", reg[reg["Factor"] == "Beta_60D_SPY"]["Group"].iloc[0] == "RELATIVE_STRENGTH")
    check("ZScore → MEAN_REVERSION", reg[reg["Factor"] == "ZScore_20D"]["Group"].iloc[0] == "MEAN_REVERSION")
    check("Fundamental_Score → FUNDAMENTAL", reg[reg["Factor"] == "Fundamental_Score"]["Group"].iloc[0] == "FUNDAMENTAL")


# ---- 12. Direction ----
def test_direction():
    reg = build_factor_registry(None)
    check("Direction 字段存在且全为 UNKNOWN（无证据）", (reg["Direction"] == "UNKNOWN").all())


# ---- 13. correlation cluster ----
def test_correlation_cluster():
    corr = pd.DataFrame([
        {"Factor_A": "Momentum_5D_Pct", "Factor_B": "Momentum_20D_Pct", "Pearson": "0.95", "Spearman": "0.94"},
        {"Factor_A": "Momentum_5D_Pct", "Factor_B": "Momentum_60D_Pct", "Pearson": "0.92", "Spearman": "0.90"},
        {"Factor_A": "RSI_14", "Factor_B": "ZScore_20D", "Pearson": "0.30", "Spearman": "0.25"},  # 不冗余
    ])
    clusters = build_factor_clusters(corr)
    check("高相关因子对成簇", len(clusters) == 2, f"got {len(clusters)}")
    check("低相关不生成簇", not ((clusters["Factor_A"] == "RSI_14") | (clusters["Factor_B"] == "RSI_14")).any())
    # 空相关
    empty = build_factor_clusters(pd.DataFrame())
    check("空相关 → 空簇", empty.empty)


# ---- 14. weight normalization（权重不伪造）----
def test_weight_normalization():
    reg = build_factor_registry(None)
    cands = build_candidate_models(reg)
    check("无证据时所有 Weight 为 None", cands["Weight"].isna().all())
    # 模型存在
    models = set(cands["Model"].unique())
    check("3 个候选模型", models == set(CANDIDATE_MODELS.keys()), f"got {models}")


# ---- 15. disabled-by-default ----
def test_disabled_by_default():
    check("QUANT_SCORE_V2_ENABLED 恒 False", QUANT_SCORE_V2_ENABLED is False)
    config = build_config({"MODEL_A_CONSERVATIVE": "NOT_ENOUGH_DATA"})
    check("config 里 ENABLED=False", config["QUANT_SCORE_V2_ENABLED"] is False)


# ---- 16. production cannot auto-enable ----
def test_no_auto_enable():
    # 即使有 PROMISING，模型状态也只能 CANDIDATE，绝不能 APPROVED/PRODUCTION
    val = make_validation({"Momentum_20D_Pct": "PROMISING"})
    reg = build_factor_registry(val)
    ms = model_statuses(reg)
    for m, s in ms.items():
        check(f"{m} 状态非 APPROVED/PRODUCTION", s in ("CANDIDATE", "DISABLED", "NOT_ENOUGH_DATA"), f"{m}={s}")
    check("有 PROMISING 时模型=CANDIDATE", all(s == "CANDIDATE" for s in ms.values()))
    # 且 QUANT_SCORE_V2_ENABLED 仍 False
    check("ENABLED 仍 False", QUANT_SCORE_V2_ENABLED is False)


# ---- 17. deterministic output ----
def test_deterministic():
    val = make_validation({"Momentum_20D_Pct": "PROMISING", "RSI_14": "REGIME_DEPENDENT"})
    r1 = build_factor_registry(val)
    r2 = build_factor_registry(val)
    pd.testing.assert_frame_equal(r1, r2)
    c1 = build_candidate_models(r1)
    c2 = build_candidate_models(r2)
    pd.testing.assert_frame_equal(c1, c2)
    check("确定性输出", True)


# ---- 18. no future data ----
def test_no_future_data():
    # 只读 validation/correlation，绝不读 Review/Exit/PnL
    reg = build_factor_registry(None)
    cols = set(reg.columns)
    check("registry 无 Exit/PnL/Review 字段", not any("Exit" in c or "PnL" in c or "Review" in c for c in cols))


# ---- 19. no AI dependency ----
def test_no_ai():
    import quant_score_v2 as q
    src = open(q.__file__).read()
    check("无 AI/ClawSocket/OpenAI 依赖", not any(k in src for k in ["ClawSocket", "openai", "anthropic", "gpt-"]))
    check("无网络请求库调用", "requests" not in src and "yfinance" not in src)


# ---- 20. old Quant_Score untouched ----
def test_old_quant_score_untouched():
    # 本模块不 import scan.py，且不产生 Quant_Score 覆盖
    import quant_score_v2 as q
    src = open(q.__file__).read()
    check("不 import scan/review", "import scan" not in src and "import review" not in src)
    check("不赋值 Quant_Score = ", "Quant_Score =" not in src)


# ---- run_quant_score_v2 端到端 ----
def test_run_end_to_end():
    tmp = tempfile.mkdtemp()
    v_path = os.path.join(tmp, "quant_factor_validation.csv")
    c_path = os.path.join(tmp, "quant_factor_correlation.csv")
    reg_path = os.path.join(tmp, "quant_factor_registry.csv")
    clu_path = os.path.join(tmp, "quant_factor_clusters.csv")
    cand_path = os.path.join(tmp, "quant_score_v2_candidates.csv")
    cfg_path = os.path.join(tmp, "quant_score_v2_config.json")
    rep_path = os.path.join(tmp, "quant_score_v2_report.json")

    # R1（STEP 3-C）：无 validation 文件（Snapshot=0 的真实场景）→ 不落任何文件
    res = run_quant_score_v2(validation_path=v_path, correlation_path=c_path,
                             registry_path=reg_path, clusters_path=clu_path,
                             candidates_path=cand_path, config_path=cfg_path, report_path=rep_path)
    check("无 validation → NOT_ENOUGH_DATA", res["status"] == "NOT_ENOUGH_DATA", f"got {res['status']}")
    check("无 validation → written=False", res.get("written") is False)
    check("无 validation → registry.csv 未创建", not os.path.exists(reg_path))
    check("无 validation → config.json 未创建", not os.path.exists(cfg_path))
    check("无 validation → report.json 未创建", not os.path.exists(rep_path))

    # 有真实 validation → 正常产出（最小合法 validation：Factor + Status 两列）
    pd.DataFrame([{"Factor": d[0], "Status": "NOT_ENOUGH_DATA"}
                  for d in FACTOR_REGISTRY_DEF]).to_csv(v_path, index=False)
    res_r = run_quant_score_v2(validation_path=v_path, correlation_path=c_path,
                               registry_path=reg_path, clusters_path=clu_path,
                               candidates_path=cand_path, config_path=cfg_path, report_path=rep_path)
    check("有 validation → OK", res_r["status"] == "OK", f"got {res_r['status']}")
    check("有 validation → written=True", res_r.get("written") is True)
    check("n_promising=0", res_r["n_promising"] == 0)

    reg = pd.read_csv(reg_path, dtype=str, keep_default_na=False)
    check("registry 24 行", len(reg) == 24)
    check("全部 BLOCKED/disabled", (reg["Evidence_Status"] == "NOT_ENOUGH_DATA").all())

    cfg = json.load(open(cfg_path))
    check("config ENABLED=false", cfg["QUANT_SCORE_V2_ENABLED"] is False)
    check("config 含 models/weights/factor_groups/normalization/eligibility_rules",
          all(k in cfg for k in ["models", "factor_groups", "normalization", "eligibility_rules"]))

    rep = json.load(open(rep_path))
    check("report state=RESEARCH", rep["state"] == "RESEARCH")
    check("report 所有 model NOT_ENOUGH_DATA",
          all(s in ("NOT_ENOUGH_DATA", "DISABLED") for s in rep["candidate_model_statuses"].values()))


# ---- STEP 3-C：Phase 4 R1 —— 无数据绝不落文件 ----
def test_no_data_no_files():
    """R1：Phase 4 在 Phase 3 无真实验证结果时必须【不创建任何文件】。

    旧行为会用全 NOT_ENOUGH_DATA 写出 5 份文件（registry/clusters/candidates/
    config/report），下游看到文件存在会误以为已产出候选模型。
    """
    tmp = tempfile.mkdtemp()
    v_path = os.path.join(tmp, "quant_factor_validation.csv")
    c_path = os.path.join(tmp, "quant_factor_correlation.csv")
    reg_path = os.path.join(tmp, "quant_factor_registry.csv")
    clu_path = os.path.join(tmp, "quant_factor_clusters.csv")
    cand_path = os.path.join(tmp, "quant_score_v2_candidates.csv")
    cfg_path = os.path.join(tmp, "quant_score_v2_config.json")
    rep_path = os.path.join(tmp, "quant_score_v2_report.json")
    outs = ((reg_path, "registry.csv"), (clu_path, "clusters.csv"),
            (cand_path, "candidates.csv"), (cfg_path, "config.json"),
            (rep_path, "report.json"))

    def none_exist(tag):
        for p, nm in outs:
            check(f"[{tag}] {nm} 未创建", not os.path.exists(p))

    # (a) validation 不存在
    ra = run_quant_score_v2(validation_path=v_path, correlation_path=c_path,
                            registry_path=reg_path, clusters_path=clu_path,
                            candidates_path=cand_path, config_path=cfg_path,
                            report_path=rep_path)
    check("(a) → NOT_ENOUGH_DATA", ra["status"] == "NOT_ENOUGH_DATA", f"got {ra['status']}")
    check("(a) written=False", ra.get("written") is False)
    none_exist("a 无 validation")

    # (b) validation 为空
    pd.DataFrame(columns=["Factor", "Status"]).to_csv(v_path, index=False)
    rb = run_quant_score_v2(validation_path=v_path, correlation_path=c_path,
                            registry_path=reg_path, clusters_path=clu_path,
                            candidates_path=cand_path, config_path=cfg_path,
                            report_path=rep_path)
    check("(b) → NOT_ENOUGH_DATA", rb["status"] == "NOT_ENOUGH_DATA", f"got {rb['status']}")
    none_exist("b 空 validation")

    # (c) 有真实 validation → 正常写出（确认不是"永远不写"）
    pd.DataFrame([{"Factor": d[0], "Status": "NOT_ENOUGH_DATA"}
                  for d in FACTOR_REGISTRY_DEF]).to_csv(v_path, index=False)
    rc = run_quant_score_v2(validation_path=v_path, correlation_path=c_path,
                            registry_path=reg_path, clusters_path=clu_path,
                            candidates_path=cand_path, config_path=cfg_path,
                            report_path=rep_path)
    check("(c) 有数据 → OK", rc["status"] == "OK", f"got {rc['status']}")
    check("(c) written=True", rc.get("written") is True)
    check("(c) registry.csv 已写且非空",
          os.path.exists(reg_path) and os.path.getsize(reg_path) > 0)

    # (d) 已存在产物 + 后续无数据 → 不删除
    before = open(reg_path, "rb").read()
    run_quant_score_v2(validation_path=os.path.join(tmp, "missing.csv"),
                       correlation_path=c_path, registry_path=reg_path,
                       clusters_path=clu_path, candidates_path=cand_path,
                       config_path=cfg_path, report_path=rep_path)
    check("(d) 已存在产物未被删除/截断", open(reg_path, "rb").read() == before)


# ---- STEP 4-8 / Phase 4：权重 None 门控 ----
# 约束：不硬编码真实事件日期；不依赖 Technical_Date 与 price history 一致（本 Phase 不涉日期）。
def _mk_registry(statuses):
    """构造 registry DataFrame：按给定 Evidence_Status 列表逐因子赋值。"""
    return pd.DataFrame([{"Factor": f, "Group": g, "Evidence_Status": s}
                         for (f, g, s) in statuses])


def test_weight_none_gate():
    """Phase 4 绝不产出数值权重 —— Weight 必须恒为 None（不给伪造权重）。"""
    statuses = [
        ("RSI_14", "MEAN_REVERSION", "PROMISING"),
        ("Momentum_20D_Pct", "MOMENTUM", "NOT_ENOUGH_DATA"),
        ("Beta_60D_SPY", "RELATIVE_STRENGTH", "INCONCLUSIVE"),
    ]
    reg = _mk_registry(statuses)

    # (1) 即使存在 PROMISING 证据，候选模型的因子权重仍必须是 None
    cand = build_candidate_models(reg)
    check("候选模型产出非空", len(cand) > 0, str(len(cand)))
    check("Weight 列恒为 None（即使有 PROMISING 证据）",
          cand["Weight"].isna().all(), str(cand["Weight"].unique()[:3]))
    check("Weight 不得出现任何数值",
          not any(isinstance(w, (int, float)) for w in cand["Weight"].tolist()))

    # (2) 证据门控：PROMISING → ELIGIBLE；其余 → BLOCKED
    by_f = {r["Factor"]: r for _, r in cand[cand["Model"] == list(CANDIDATE_MODELS)[0]].iterrows()}
    check("PROMISING → ELIGIBLE", by_f["RSI_14"]["Candidate_Status"] == "ELIGIBLE",
          str(by_f["RSI_14"]["Candidate_Status"]))
    check("NOT_ENOUGH_DATA → BLOCKED",
          by_f["Momentum_20D_Pct"]["Candidate_Status"] == "BLOCKED",
          str(by_f["Momentum_20D_Pct"]["Candidate_Status"]))
    check("INCONCLUSIVE → BLOCKED", by_f["Beta_60D_SPY"]["Candidate_Status"] == "BLOCKED",
          str(by_f["Beta_60D_SPY"]["Candidate_Status"]))

    # (3) 三个模型都必须各自产出候选清单
    check("三模型全覆盖", set(cand["Model"]) == set(CANDIDATE_MODELS),
          str(sorted(set(cand["Model"]))))

    # (4) 模型状态三分支
    s_none = model_statuses(_mk_registry([("RSI_14", "MEAN_REVERSION", "NOT_ENOUGH_DATA"),
                                          ("Momentum_20D_Pct", "MOMENTUM", "INCONCLUSIVE")]))
    check("无 PROMISING/REGIME_DEPENDENT → 全 NOT_ENOUGH_DATA",
          all(v == "NOT_ENOUGH_DATA" for v in s_none.values()), str(s_none))
    s_reg = model_statuses(_mk_registry([("RSI_14", "MEAN_REVERSION", "REGIME_DEPENDENT")]))
    check("仅 REGIME_DEPENDENT → DISABLED", all(v == "DISABLED" for v in s_reg.values()), str(s_reg))
    s_pro = model_statuses(_mk_registry([("RSI_14", "MEAN_REVERSION", "PROMISING")]))
    check("有 PROMISING → CANDIDATE", all(v == "CANDIDATE" for v in s_pro.values()), str(s_pro))

    # (5) group_weights 是"研究规格"常量（有定义且冻结），与 Weight=None 是两回事
    for m, spec in CANDIDATE_MODELS.items():
        check("%s group_weights 已定义且非空" % m, bool(spec.get("group_weights")))

    # (6) V2 恒关闭：config 里 QUANT_SCORE_V2_ENABLED 必须为 False（任何证据下）
    for st, label in ((s_none, "无证据"), (s_pro, "有 PROMISING 证据")):
        cfg = build_config(st)
        check("config ENABLED=False（%s）" % label,
              cfg["QUANT_SCORE_V2_ENABLED"] is False)


def main():
    _tests = [
        test_empty_validation,
        test_evidence_gate,
        test_candidate_blocking_and_eligibility,
        test_registry_grouping,
        test_direction,
        test_correlation_cluster,
        test_weight_normalization,
        test_disabled_by_default,
        test_no_auto_enable,
        test_deterministic,
        test_no_future_data,
        test_no_ai,
        test_old_quant_score_untouched,
        test_run_end_to_end,
        # ---- STEP 3-C ----
        test_no_data_no_files,
        # ---- STEP 4-8 / Phase 4 ----
        test_weight_none_gate,
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
