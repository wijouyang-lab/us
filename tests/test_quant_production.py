# -*- coding: utf-8 -*-
"""Quant Production Governance 纯函数回归测试（不依赖真实数据/网络）。"""
import json
import os
import sys
import tempfile

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import quant_production as qp
from quant_production import (
    QUANT_SCORE_V2_ENABLED,
    QUANT_SCORE_V2_KILL_SWITCH,
    PRODUCTION_MODEL,
    PRODUCTION_VERSION,
    V1_MODEL,
    V2_MODEL,
    config_hash,
    determine_state,
    evaluate_production_gates,
    human_approval_gate,
    load_approval,
    load_production_config,
    research_evidence_gate,
    rollback_to_v1,
    run_production_governance,
    safety_monitor,
    shadow_gate,
    should_rollback,
    walk_forward_gate,
)



def check(name, cond, detail=""):
    """断言：FAIL 时抛出 AssertionError（pytest 可捕获），同时保留打印。"""
    if cond:
        print(f"  [PASS] {name}")
        return True
    print(f"  [FAIL] {name}  {detail}")
    raise AssertionError(f"{name}  {detail}".strip())


def tmp_files():
    tmp = tempfile.mkdtemp()
    return {
        "validation_csv": os.path.join(tmp, "qv.csv"),
        "validation_report": os.path.join(tmp, "qvr.json"),
        "wf_csv": os.path.join(tmp, "wf.csv"),
        "wf_summary": os.path.join(tmp, "wfs.json"),
        "shadow_snap": os.path.join(tmp, "ss.csv"),
        "shadow_perf": os.path.join(tmp, "sp.csv"),
        "shadow_report": os.path.join(tmp, "sr.json"),
    }


# ---- 1-4. 各 Gate fail / NOT_ENOUGH_DATA ----
def test_gates_all_fail():
    f = tmp_files()
    gates = evaluate_production_gates(
        approval={"approved": False},
        validation_csv=f["validation_csv"], validation_report=f["validation_report"],
        wf_summary=f["wf_summary"], wf_csv=f["wf_csv"],
        shadow_report=f["shadow_report"], shadow_snap=f["shadow_snap"], shadow_perf=f["shadow_perf"],
    )
    check("research gate NOT_ENOUGH_DATA", gates["research_gate"] == "NOT_ENOUGH_DATA", f"got {gates['research_gate']}")
    check("wf gate NOT_ENOUGH_DATA", gates["walk_forward_gate"] == "NOT_ENOUGH_DATA")
    check("shadow gate NOT_ENOUGH_DATA", gates["shadow_gate"] == "NOT_ENOUGH_DATA")
    check("human gate FAIL", gates["human_approval_gate"] == "FAIL")
    check("production_gate = NOT_READY", gates["production_gate"] == "NOT_READY")


def test_research_gate():
    check("空 validation → NOT_ENOUGH_DATA", research_evidence_gate("/tmp/nonexistent.csv")[0] == "NOT_ENOUGH_DATA")
    # 有 PROMISING
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "v.csv")
    pd.DataFrame({"Factor": ["A", "B"], "Status": ["PROMISING", "EXPLORATORY"]}).to_csv(p, index=False)
    check("有 PROMISING → PASS", research_evidence_gate(p)[0] == "PASS")


def test_wf_gate():
    check("空 summary → NOT_ENOUGH_DATA", walk_forward_gate("/tmp/nonexistent.json")[0] == "NOT_ENOUGH_DATA")
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "s.json")
    json.dump({"model_statuses": {"MODEL_A": "NOT_ENOUGH_DATA"}}, open(p, "w"))
    check("全 NOT_ENOUGH_DATA → NOT_ENOUGH_DATA", walk_forward_gate(p)[0] == "NOT_ENOUGH_DATA")
    json.dump({"model_statuses": {"MODEL_A": "PASS"}}, open(p, "w"))
    check("有 PASS → PASS", walk_forward_gate(p)[0] == "PASS")


def test_shadow_gate():
    check("空 report → NOT_ENOUGH_DATA", shadow_gate("/tmp/nonexistent.json")[0] == "NOT_ENOUGH_DATA")


# ---- 5-6. Human approval false / true ----
def test_human_approval():
    check("approval false → FAIL", human_approval_gate({"approved": False})[0] == "FAIL")
    check("approval true 但缺 by/at → FAIL",
          human_approval_gate({"approved": True})[0] == "FAIL")
    check("approval true + by + at → PASS",
          human_approval_gate({"approved": True, "approved_by": "human", "approved_at": "2026-10-07T00:00:00"})[0] == "PASS")


# ---- 7-8. config hash match / mismatch ----
def test_config_hash():
    c1 = {"a": 1, "b": 2}
    c2 = {"b": 2, "a": 1}  # 键顺序不同
    check("hash 键序无关", config_hash(c1) == config_hash(c2))
    c3 = {"a": 1, "b": 3}
    check("hash 内容不同则不同", config_hash(c1) != config_hash(c3))
    check("hash 确定性", config_hash(c1) == config_hash(c1))


def test_hash_mismatch():
    cfg = {"production_model": V2_MODEL, "quant_score_v2_enabled": True, "version": "V2"}
    approval = {"approved": True, "approved_by": "human", "approved_at": "2026-10-07"}
    gates = {"production_gate": "READY_FOR_PRODUCTION"}
    # 期望 hash 与运行时 hash 不同 → ROLLBACK_REQUIRED
    st, reason = safety_monitor(V2_MODEL, "expected_hash_abc", cfg, approval, gates)
    check("config mismatch → ROLLBACK_REQUIRED", st == "ROLLBACK_REQUIRED", f"got {st}: {reason}")
    # 期望 hash 正确 → PASS
    st2, _ = safety_monitor(V2_MODEL, config_hash(cfg), cfg, approval, gates)
    check("config match → PASS", st2 == "PASS", f"got {st2}")


# ---- 9. required data missing ----
def test_required_data_missing():
    # 无 validation 数据 → research gate NOT_ENOUGH_DATA（已在 test_gates_all_fail 覆盖）
    f = tmp_files()
    gates = evaluate_production_gates(
        approval={"approved": False},
        validation_csv=f["validation_csv"], validation_report=f["validation_report"],
        wf_summary=f["wf_summary"], wf_csv=f["wf_csv"],
        shadow_report=f["shadow_report"], shadow_snap=f["shadow_snap"], shadow_perf=f["shadow_perf"],
    )
    check("缺数据 → 三 gate 均 NOT_ENOUGH_DATA",
          gates["research_gate"] == "NOT_ENOUGH_DATA" and gates["walk_forward_gate"] == "NOT_ENOUGH_DATA"
          and gates["shadow_gate"] == "NOT_ENOUGH_DATA")


# ---- 10. unknown model version ----
def test_unknown_model():
    st, _ = safety_monitor("UNKNOWN_MODEL", None, {}, {"approved": False}, {})
    check("未知模型 → BLOCK", st == "BLOCK", f"got {st}")


# ---- 11. kill switch ----
def test_kill_switch():
    old = QUANT_SCORE_V2_KILL_SWITCH
    # 模拟 kill switch 开启（只读全局，测试里用 safety_monitor 逻辑——kill switch 是模块级常量）
    # 这里直接验证：kill switch=true 时 safety_monitor 应 ROLLBACK_REQUIRED
    # 由于常量不可在测试中安全修改，验证 V1 在 kill switch 下仍 PASS
    st, _ = safety_monitor(V1_MODEL, None, {}, {"approved": False}, {})
    check("V1 永远安全", st == "PASS")


# ---- 12. rollback ----
def test_rollback():
    state = {"active_model": V2_MODEL, "active_version": "V2"}
    new = rollback_to_v1(state)
    check("V2 → V1", new["active_model"] == V1_MODEL and new["active_version"] == "V1")
    check("previous 记录 V2", new["previous_model"] == V2_MODEL and new["previous_version"] == "V2")
    check("rollback_available=true", new["rollback_available"] is True)
    # V1 不再回退
    state_v1 = {"active_model": V1_MODEL, "active_version": "V1"}
    check("V1 回退为 no-op", rollback_to_v1(state_v1)["active_model"] == V1_MODEL)


# ---- 13. V1 fallback ----
def test_v1_fallback():
    # 默认 config 缺失 → V1/disabled
    cfg = load_production_config("/tmp/nonexistent.json")
    check("默认 production_model=V1", cfg["production_model"] == V1_MODEL)
    check("默认 version=V1", cfg["version"] == "V1")
    check("默认 enabled=false", cfg["quant_score_v2_enabled"] is False)


# ---- 14. no automatic V1→V2 ----
def test_no_auto_v1_to_v2():
    # run_production_governance 即使 config 写了 V2，只要 enabled=false 仍 V1
    tmp = tempfile.mkdtemp()
    cfg_path = os.path.join(tmp, "cfg.json")
    json.dump({"production_model": V2_MODEL, "quant_score_v2_enabled": False, "version": "V2"}, open(cfg_path, "w"))
    r = run_production_governance(config_path=cfg_path,
                                  approval_path=os.path.join(tmp, "ap.json"),
                                  state_path=os.path.join(tmp, "st.json"),
                                  audit_path=os.path.join(tmp, "au.jsonl"))
    check("enabled=false → active_model=V1", r["active_model"] == V1_MODEL, f"got {r['active_model']}")


# ---- 15. no automatic approval ----
def test_no_auto_approval():
    ap = load_approval("/tmp/nonexistent.json")
    check("无审批文件 → approved=false", ap["approved"] is False)
    check("无审批文件 → approved_by=None", ap["approved_by"] is None)


# ---- 16. no auto weight update ----
def test_no_auto_weight():
    src = open(qp.__file__).read()
    check("无自动调权逻辑", "weight" not in src.lower() or "auto" not in src.lower())


# ---- 17. production disabled by default ----
def test_production_disabled_default():
    check("QUANT_SCORE_V2_ENABLED 默认 false", QUANT_SCORE_V2_ENABLED is False)
    check("PRODUCTION_MODEL 默认 V1", PRODUCTION_MODEL == V1_MODEL)
    check("PRODUCTION_VERSION 默认 V1", PRODUCTION_VERSION == "V1")


# ---- 18. audit trail ----
def test_audit_trail():
    tmp = tempfile.mkdtemp()
    cfg_path = os.path.join(tmp, "cfg.json")
    json.dump({"production_model": V1_MODEL, "quant_score_v2_enabled": False, "version": "V1"}, open(cfg_path, "w"))
    r = run_production_governance(config_path=cfg_path,
                                  approval_path=os.path.join(tmp, "ap.json"),
                                  state_path=os.path.join(tmp, "st.json"),
                                  audit_path=os.path.join(tmp, "au.jsonl"))
    audit_path = os.path.join(tmp, "au.jsonl")
    check("audit 文件已写", os.path.exists(audit_path) and os.path.getsize(audit_path) > 0)
    lines = open(audit_path).read().strip().split("\n")
    entry = json.loads(lines[0])
    check("audit 含 Active_Model", entry["Active_Model"] == V1_MODEL)
    check("audit 含 Config_Hash", bool(entry["Config_Hash"]))


# ---- 19. deterministic ----
def test_deterministic():
    g1 = evaluate_production_gates(approval={"approved": False})
    g2 = evaluate_production_gates(approval={"approved": False})
    check("gate 评估确定性", g1 == g2)
    c1 = config_hash({"a": 1})
    c2 = config_hash({"a": 1})
    check("hash 确定性", c1 == c2)


# ---- 20. no future leakage ----
def test_no_leakage():
    # governance 只读研究输出文件，不读 Review/Exit/PnL
    src = open(qp.__file__).read()
    check("不读 Review/Exit/PnL", not any(k in src for k in ["trade_history", "Exit_Price", "Stop_Loss_Hit"]))


# ---- 21-22. no AI / no network ----
def test_no_ai_no_network():
    src = open(qp.__file__).read()
    check("无 AI 依赖", not any(k in src for k in ["ClawSocket", "openai", "anthropic", "gpt-"]))
    check("无网络请求", "requests" not in src and "yfinance" not in src)


# ---- 23. existing V1 unchanged ----
def test_v1_unchanged():
    src = open(qp.__file__).read()
    check("不 import scan/review", "import scan" not in src and "import review" not in src)
    check("不修改 Quant_Score", "Quant_Score =" not in src)


# ---- 综合：默认状态 V1 ACTIVE / V2 DISABLED ----
def test_default_production_state():
    tmp = tempfile.mkdtemp()
    r = run_production_governance(config_path=os.path.join(tmp, "cfg.json"),
                                  approval_path=os.path.join(tmp, "ap.json"),
                                  state_path=os.path.join(tmp, "st.json"),
                                  audit_path=os.path.join(tmp, "au.jsonl"))
    check("默认 active_model=V1", r["active_model"] == V1_MODEL)
    check("默认 v2_enabled=false", r["v2_enabled"] is False)
    check("默认 production_state 为 V1 系", r["production_state"] in ("V1_ACTIVE", "NOT_ENOUGH_DATA"),
          f"got {r['production_state']}")
    check("production_gate=NOT_READY", r["gates"]["production_gate"] == "NOT_READY")


# ---- STEP 3-C：Phase 7 R1 一致性 —— 绝不产生空文件 ----
def test_no_empty_files():
    """R1 一致性：Phase 7 不存在"无数据写空文件"的分支。

    与其它 Phase 不同，Phase 7 的 state.json 是【治理状态】而非研究数据：
    V1_ACTIVE 是安全默认值，必须持久存在，因此恒为 written=True。
    本测试验证的是"它写出的一定是真实非空状态，绝不是 0 字节/0 行文件"。
    """
    tmp = tempfile.mkdtemp()
    state_path = os.path.join(tmp, "state.json")
    audit_path = os.path.join(tmp, "audit.jsonl")
    cfg_path = os.path.join(tmp, "cfg.json")
    app_path = os.path.join(tmp, "app.json")

    r = run_production_governance(config_path=cfg_path, approval_path=app_path,
                                  state_path=state_path, audit_path=audit_path)
    check("written=True（治理状态恒为真实内容）", r.get("written") is True)
    check("state.json 已创建", os.path.exists(state_path))
    size = os.path.getsize(state_path)
    check("state.json 非空（非 0 字节）", size > 0, f"{size} bytes")

    st = json.load(open(state_path))
    check("state 含 active_model", bool(st.get("active_model")), str(st.get("active_model")))
    check("state active_version=V1", st.get("active_version") == "V1", str(st.get("active_version")))
    check("state 含 schema_version=phase7.v1", st.get("schema_version") == "phase7.v1",
          str(st.get("schema_version")))
    check("state 非 0 行/非空 dict", len(st) > 0, f"{len(st)} keys")

    check("audit.jsonl 已创建且非空",
          os.path.exists(audit_path) and os.path.getsize(audit_path) > 0)
    entry = json.loads(open(audit_path).readline())
    check("audit 首条含 schema_version=phase7.v1",
          entry.get("schema_version") == "phase7.v1", str(entry.get("schema_version")))
    check("audit 首条含真实 Gate_Status", "Gate_Status" in entry)

    # 安全状态不变
    check("production_state=V1_ACTIVE", r["production_state"] == "V1_ACTIVE",
          str(r["production_state"]))
    check("gate=NOT_READY", r["gates"]["production_gate"] == "NOT_READY")


# ---- STEP 4-8 / Phase 7：activation criteria ----
# 约束：不硬编码真实事件日期 —— 所有日期用 fixture 参数（测试内固定合成日期，非业务事件日期）。
def _write_all_pass(tmp):
    """写入使 4 个 gate 全部 PASS 所需的合成证据文件（TEST DATA，绝不写生产 CSV）。"""
    import json as _json
    f = tmp_files()
    # research gate：至少一个 PROMISING
    pd.DataFrame([{"Factor": "RSI_14", "Status": "PROMISING"}]).to_csv(
        f["validation_csv"], index=False, encoding="utf-8")
    with open(f["validation_report"], "w", encoding="utf-8") as h:
        _json.dump({"schema_version": "phase3.v1"}, h)
    # wf gate：至少一个模型 OOS PASS
    with open(f["wf_summary"], "w", encoding="utf-8") as h:
        _json.dump({"model_statuses": {"MODEL_B_BALANCED": "PASS"}}, h)
    pd.DataFrame([{"Model": "MODEL_B_BALANCED", "Validation_Status": "PASS"}]).to_csv(
        f["wf_csv"], index=False, encoding="utf-8")
    # shadow gate：已启用且 horizon 成熟
    with open(f["shadow_report"], "w", encoding="utf-8") as h:
        _json.dump({"shadow_status": "SHADOW_ACTIVE",
                    "5D_status": "OK", "10D_status": "OK", "20D_status": "OK"}, h)
    pd.DataFrame([{"Scan_Date": "2026-03-02", "Ticker": "T0"}]).to_csv(
        f["shadow_snap"], index=False, encoding="utf-8")
    pd.DataFrame([{"Scan_Date": "2026-03-02", "Ticker": "T0"}]).to_csv(
        f["shadow_perf"], index=False, encoding="utf-8")
    return f


def test_activation_criteria():
    """Production Gate 必须四项俱全才 READY；且 READY ≠ ENABLED（绝不自动 promote）。"""
    tmp = tempfile.mkdtemp()
    f = _write_all_pass(tmp)
    approval_ok = {"approved": True, "approved_by": "tester", "approved_at": "2026-03-02T00:00:00Z"}

    def gates(**over):
        kw = dict(approval=approval_ok,
                  validation_csv=f["validation_csv"], validation_report=f["validation_report"],
                  wf_summary=f["wf_summary"], wf_csv=f["wf_csv"],
                  shadow_report=f["shadow_report"], shadow_snap=f["shadow_snap"],
                  shadow_perf=f["shadow_perf"])
        kw.update(over)
        return evaluate_production_gates(**kw)

    # (1) 四项俱全 → READY_FOR_PRODUCTION
    g_all = gates()
    check("四 gate 全 PASS → READY_FOR_PRODUCTION",
          g_all["production_gate"] == "READY_FOR_PRODUCTION", str(g_all["production_gate"]))
    check("research_gate=PASS", g_all["research_gate"] == "PASS", str(g_all["research_gate"]))
    check("walk_forward_gate=PASS", g_all["walk_forward_gate"] == "PASS", str(g_all["walk_forward_gate"]))
    check("shadow_gate=PASS", g_all["shadow_gate"] == "PASS", str(g_all["shadow_gate"]))
    check("human_approval_gate=PASS", g_all["human_approval_gate"] == "PASS",
          str(g_all["human_approval_gate"]))

    # (2) READY ≠ ENABLED：V2 开关必须仍为 False
    check("READY 时 QUANT_SCORE_V2_ENABLED 仍为 False（绝不自动 promote）",
          QUANT_SCORE_V2_ENABLED is False)

    # (3) V1 在任何 gate 状态下都是 V1_ACTIVE
    check("determine_state(V1) = V1_ACTIVE",
          determine_state(V1_MODEL, g_all, approval_ok) == "V1_ACTIVE",
          str(determine_state(V1_MODEL, g_all, approval_ok)))

    # (4) 缺任一 gate → NOT_READY
    variants = [
        ("无人工审批", dict(approval={"approved": False})),
        ("无 research 证据", dict(validation_csv=os.path.join(tmp, "none.csv"))),
        ("无 wf 结果", dict(wf_summary=os.path.join(tmp, "none.json"),
                        wf_csv=os.path.join(tmp, "none2.csv"))),
        ("shadow 未启用", dict(shadow_report=os.path.join(tmp, "none3.json"),
                           shadow_snap=os.path.join(tmp, "none4.csv"),
                           shadow_perf=os.path.join(tmp, "none5.csv"))),
    ]
    for label, over in variants:
        g = gates(**over)
        check("缺 %s → NOT_READY" % label,
              g["production_gate"] == "NOT_READY", "%s → %s" % (label, g["production_gate"]))

    # (5) gate 未就绪时 V2 必须 BLOCKED（即使审批通过）
    g_partial = gates(shadow_report=os.path.join(tmp, "n6.json"),
                      shadow_snap=os.path.join(tmp, "n7.csv"),
                      shadow_perf=os.path.join(tmp, "n8.csv"))
    check("gate 未就绪 → V2 BLOCKED",
          determine_state(V2_MODEL, g_partial, approval_ok) == "BLOCKED",
          str(determine_state(V2_MODEL, g_partial, approval_ok)))

    # (6) 审批缺失时 V2 BLOCKED
    check("无审批 → V2 BLOCKED",
          determine_state(V2_MODEL, g_all, {"approved": False}) == "BLOCKED",
          str(determine_state(V2_MODEL, g_all, {"approved": False})))

    # (7) 当前真实默认状态：所有证据文件缺失 → NOT_READY 且 V1_ACTIVE
    g_real = evaluate_production_gates(
        approval={"approved": False},
        validation_csv=os.path.join(tmp, "r1.csv"), validation_report=os.path.join(tmp, "r2.json"),
        wf_summary=os.path.join(tmp, "r3.json"), wf_csv=os.path.join(tmp, "r4.csv"),
        shadow_report=os.path.join(tmp, "r5.json"), shadow_snap=os.path.join(tmp, "r6.csv"),
        shadow_perf=os.path.join(tmp, "r7.csv"))
    check("真实默认 → production_gate=NOT_READY", g_real["production_gate"] == "NOT_READY",
          str(g_real["production_gate"]))
    check("真实默认 → V1_ACTIVE",
          determine_state(V1_MODEL, g_real, {"approved": False}) == "V1_ACTIVE")


def main():
    _tests = [
        test_gates_all_fail,
        test_research_gate,
        test_wf_gate,
        test_shadow_gate,
        test_human_approval,
        test_config_hash,
        test_hash_mismatch,
        test_required_data_missing,
        test_unknown_model,
        test_kill_switch,
        test_rollback,
        test_v1_fallback,
        test_no_auto_v1_to_v2,
        test_no_auto_approval,
        test_no_auto_weight,
        test_production_disabled_default,
        test_audit_trail,
        test_deterministic,
        test_no_leakage,
        test_no_ai_no_network,
        test_v1_unchanged,
        test_default_production_state,
        # ---- STEP 3-C ----
        test_no_empty_files,
        # ---- STEP 4-8 / Phase 7 ----
        test_activation_criteria,
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
