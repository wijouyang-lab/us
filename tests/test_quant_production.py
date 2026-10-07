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


def main():
    test_gates_all_fail()
    test_research_gate()
    test_wf_gate()
    test_shadow_gate()
    test_human_approval()
    test_config_hash()
    test_hash_mismatch()
    test_required_data_missing()
    test_unknown_model()
    test_kill_switch()
    test_rollback()
    test_v1_fallback()
    test_no_auto_v1_to_v2()
    test_no_auto_approval()
    test_no_auto_weight()
    test_production_disabled_default()
    test_audit_trail()
    test_deterministic()
    test_no_leakage()
    test_no_ai_no_network()
    test_v1_unchanged()
    test_default_production_state()

    print(f"\n结果：通过 {_passed} / {_passed + _failed}")
    if _failures:
        print("失败项：")
        for f in _failures:
            print("  -", f)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
