# -*- coding: utf-8 -*-
"""
Quant Score V2 Production Integration & Governance —— 阶段 7（治理层，非交易层）。

【定位】
    建立安全、可审计、可回滚、需人工批准的生产切换系统。
    今天完成的是 PRODUCTION GOVERNANCE ARCHITECTURE，不是 PRODUCTION MODEL APPROVAL。

【绝对原则（默认值）】
    QUANT_SCORE_V2_ENABLED = false
    PRODUCTION_MODEL       = CURRENT_EXISTING_QUANT_SCORE
    PRODUCTION_VERSION     = V1
    ROLLBACK_AVAILABLE     = true
    程序绝不自动：enable V2 / replace V1 / approve V2 / increase V2 weight /
    disable V1 / delete V1 / modify Scan strategy。

【Production State Machine（不得跳过中间阶段）】
    RESEARCH → CANDIDATE → OOS_VALIDATED → SHADOW → READY_FOR_PRODUCTION
    → HUMAN_APPROVED → PRODUCTION_ACTIVE → ROLLED_BACK
    失败状态：NOT_ENOUGH_DATA / INCONCLUSIVE / REJECTED / BLOCKED

【Production Gate（4 层，全部通过才 READY_FOR_PRODUCTION）】
    RESEARCH_EVIDENCE_GATE（Phase 3）
    WALK_FORWARD_GATE     （Phase 5）
    SHADOW_GATE           （Phase 6）
    HUMAN_APPROVAL_GATE   （人工审批文件）
    注意：READY_FOR_PRODUCTION ≠ ENABLED。

【Kill Switch / Rollback】
    QUANT_SCORE_V2_KILL_SWITCH = false（默认）。
    kill switch=true → V2 永久阻止运行，若已运行立即回退 V1；不允许自动恢复，必须人工关闭。
    rollback：V2 → V1 确定性、快速、无需重训、无需 AI。
    系统只能自动退出风险（V2→V1），绝不能自动升级风险（V1→V2）。

【AI / 网络】
    AI Calls = 0，网络请求 = 0。只读本仓库已有数据和配置。
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

# ============================================================================
# 全局默认状态（恒安全默认，绝不自动翻转）
# ============================================================================
QUANT_SCORE_V2_ENABLED = False
QUANT_SCORE_V2_KILL_SWITCH = False

PRODUCTION_MODEL = "CURRENT_EXISTING_QUANT_SCORE"
PRODUCTION_VERSION = "V1"
ROLLBACK_AVAILABLE = True

APPROVAL_PATH = "quant_production_approval.json"
CONFIG_PATH = "quant_production_config.json"
STATE_PATH = "quant_production_state.json"
AUDIT_PATH = "quant_production_audit.jsonl"

VALIDATION_CSV = "quant_factor_validation.csv"
VALIDATION_REPORT = "quant_factor_validation_report.json"
WALK_FORWARD_CSV = "quant_walk_forward_results.csv"
WALK_FORWARD_SUMMARY = "quant_walk_forward_summary.json"
SHADOW_SNAPSHOT = "quant_shadow_snapshot.csv"
SHADOW_PERFORMANCE = "quant_shadow_performance.csv"
SHADOW_REPORT = "quant_shadow_report.json"

V1_MODEL = "CURRENT_EXISTING_QUANT_SCORE"
V2_MODEL = "QUANT_SCORE_V2_CANDIDATE"

# 输出 schema 版本（STEP 3-A）：写入 state.json / config（默认）/ audit.jsonl。
# 命名规则：phase<阶段>.v<主版本>，与 Phase 1–7 完全一致；字段结构变更时递增主版本号。
# 注意：PRODUCTION_VERSION("V1") 是【模型版本】，与 schema_version（【数据结构版本】）语义不同，不可混用。
SCHEMA_VERSION = "phase7.v1"

# 状态机
STATES = [
    "RESEARCH", "CANDIDATE", "OOS_VALIDATED", "SHADOW",
    "READY_FOR_PRODUCTION", "HUMAN_APPROVED", "PRODUCTION_ACTIVE", "ROLLED_BACK",
]
FAILURE_STATES = ["NOT_ENOUGH_DATA", "INCONCLUSIVE", "REJECTED", "BLOCKED"]

# 安全回退触发条件（只能 V2→V1，禁止 V1→V2）
SAFETY_ROLLBACK_TRIGGERS = [
    "CONFIG_MISMATCH", "INVALID_OUTPUT", "MISSING_REQUIRED_DATA",
    "RUNTIME_ERROR", "PRODUCTION_GATE_FAIL", "KILL_SWITCH",
]


def _to_float(v):
    try:
        f = float(v)
        if np.isnan(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _read_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _read_csv(path):
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str, keep_default_na=False)
    except Exception:
        return pd.DataFrame()


# ============================================================================
# 1. Config Hash（用于确认运行配置 == 批准配置）
# ============================================================================
def config_hash(config_dict):
    """对配置 dict 计算确定性 SHA256（键排序，避免顺序敏感）。"""
    payload = json.dumps(config_dict, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_production_config(path=CONFIG_PATH):
    """读取生产配置；不存在则返回默认 V1/disabled 配置。"""
    default = {
        "schema_version": SCHEMA_VERSION,
        "production_model": PRODUCTION_MODEL,
        "quant_score_v2_enabled": False,
        "version": PRODUCTION_VERSION,
        "rollback_enabled": True,
        "config_hash": None,
    }
    cfg = _read_json(path)
    if not cfg:
        return default
    return {**default, **cfg}


# ============================================================================
# 2. 人工审批
# ============================================================================
def load_approval(path=APPROVAL_PATH):
    """读取人工审批文件；不存在或 approved!=true 则视为未批准。"""
    default = {
        "approved": False,
        "approved_model": None,
        "approved_version": None,
        "approved_by": None,
        "approved_at": None,
        "reason": None,
        "expiry_date": None,
    }
    ap = _read_json(path)
    if not ap:
        return default
    return {**default, **ap}


def human_approval_gate(approval, now=None):
    """人工审批 Gate：approved==true 且未过期 → PASS，否则 FAIL。"""
    if not approval or approval.get("approved") is not True:
        return "FAIL", "approval=false（未人工批准）"
    expiry = approval.get("expiry_date")
    if expiry:
        try:
            if datetime.now() > datetime.fromisoformat(str(expiry)):
                return "FAIL", f"审批已过期（expiry={expiry}）"
        except Exception:
            pass
    # 必须有审批人 + 时间（不能由 AI/workflow 自动生成）
    if not approval.get("approved_by") or not approval.get("approved_at"):
        return "FAIL", "缺少 approved_by / approved_at（不得自动生成）"
    return "PASS", "人工审批通过"


# ============================================================================
# 3. Research Evidence Gate（Phase 3）
# ============================================================================
def research_evidence_gate(validation_csv_path=VALIDATION_CSV, report_path=VALIDATION_REPORT):
    """检查 Phase 3 证据。NOT_ENOUGH_DATA / 无 PROMISING → FAIL。"""
    df = _read_csv(validation_csv_path)
    report = _read_json(report_path)
    if df.empty:
        return "NOT_ENOUGH_DATA", "无 quant_factor_validation.csv（Snapshot=0）"
    if "Status" not in df.columns:
        return "FAIL", "validation.csv 缺少 Status 列"
    statuses = df["Status"].tolist()
    if all(s in ("NOT_ENOUGH_DATA", "") for s in statuses):
        return "NOT_ENOUGH_DATA", "全部因子 NOT_ENOUGH_DATA"
    if not any(s == "PROMISING" for s in statuses):
        return "FAIL", "无任何 PROMISING 因子（证据不足，禁止生产）"
    # 有 PROMISING 但不代表通过——需结合单调性/regime/样本量综合判断
    n_promising = statuses.count("PROMISING")
    return "PASS", f"存在 {n_promising} 个 PROMISING 因子（仅研究证据，非生产批准）"


# ============================================================================
# 4. Walk-Forward Gate（Phase 5）
# ============================================================================
def walk_forward_gate(summary_path=WALK_FORWARD_SUMMARY, results_csv=WALK_FORWARD_CSV):
    """检查 Phase 5 OOS 证据。读取现有配置，不自行修改门槛。"""
    summary = _read_json(summary_path)
    df = _read_csv(results_csv)
    if not summary and df.empty:
        return "NOT_ENOUGH_DATA", "无 walk-forward 结果（数据不足）"
    # 读取 Phase 5 summary 的 model statuses
    model_statuses = summary.get("model_statuses", {}) if summary else {}
    if not model_statuses:
        return "NOT_ENOUGH_DATA", "walk-forward summary 无 model_statuses"
    has_pass = any(v == "PASS" for v in model_statuses.values())
    all_ned = all(v in ("NOT_ENOUGH_DATA",) for v in model_statuses.values())
    if all_ned:
        return "NOT_ENOUGH_DATA", "所有模型 NOT_ENOUGH_DATA（无 OOS 数据）"
    if not has_pass:
        return "FAIL", "无任何模型 OOS PASS"
    return "PASS", f"存在 OOS PASS 模型（OOS 证据，非生产批准）"


# ============================================================================
# 5. Shadow Gate（Phase 6）
# ============================================================================
def shadow_gate(report_path=SHADOW_REPORT, snapshot_csv=SHADOW_SNAPSHOT, performance_csv=SHADOW_PERFORMANCE):
    """检查 Phase 6 真实 shadow 证据。数据不足 → NOT_ENOUGH_DATA，绝不自动 PASS。"""
    report = _read_json(report_path)
    snap = _read_csv(snapshot_csv)
    perf = _read_csv(performance_csv)
    if snap.empty and perf.empty and not report:
        return "NOT_ENOUGH_DATA", "无 shadow 数据（Snapshot=0）"
    status = report.get("shadow_status", "") if report else ""
    if status == "SHADOW_DISABLED":
        return "NOT_ENOUGH_DATA", "shadow 未启用（SHADOW_DISABLED）"
    # 检查 shadow 运行记录
    run_dates = snap["Scan_Date"].nunique() if "Scan_Date" in snap.columns else 0
    if run_dates < 1:
        return "NOT_ENOUGH_DATA", "shadow 无运行记录"
    # 检查 5D/10D/20D 成熟度
    for h in ("5D", "10D", "20D"):
        st = report.get(f"{h}_status")
        if st == "NOT_ENOUGH_DATA":
            return "NOT_ENOUGH_DATA", f"{h} forward return 未成熟"
    return "PASS", f"shadow 运行 {run_dates} 天，horizon 均成熟（研究证据）"


# ============================================================================
# 6. Safety Monitor
# ============================================================================
def safety_monitor(active_model, expected_config_hash, runtime_config, approval, gates):
    """检查生产安全。返回 (status, reason)。默认无法确认安全 → BLOCK。

    status ∈ PASS / WARNING / BLOCK / ROLLBACK_REQUIRED
    """
    # 1. Kill switch
    if QUANT_SCORE_V2_KILL_SWITCH:
        return "ROLLBACK_REQUIRED", "QUANT_SCORE_V2_KILL_SWITCH=true，强制回退 V1"

    # 2. 未知模型版本
    if active_model not in (V1_MODEL, V2_MODEL):
        return "BLOCK", f"未知模型版本：{active_model}"

    # 3. 当前是 V1 → 永远安全
    if active_model == V1_MODEL:
        return "PASS", "V1 为安全默认版本"

    # 4. 当前是 V2 → 必须逐项确认
    if active_model == V2_MODEL:
        # config hash 匹配
        runtime_hash = config_hash(runtime_config)
        if expected_config_hash and runtime_hash != expected_config_hash:
            return "ROLLBACK_REQUIRED", "CONFIG_MISMATCH（运行配置 != 批准配置）"
        # 人工审批
        if approval.get("approved") is not True:
            return "ROLLBACK_REQUIRED", "V2 运行但审批已撤销/缺失"
        # gate 状态
        if gates.get("production_gate") != "READY_FOR_PRODUCTION":
            return "ROLLBACK_REQUIRED", "PRODUCTION_GATE_FAIL（gate 不再满足）"
        return "PASS", "V2 运行安全（config 匹配 + 审批 + gate 通过）"

    return "BLOCK", "无法确认安全"


# ============================================================================
# 7. 综合 Production Gate
# ============================================================================
def evaluate_production_gates(approval=None, validation_csv=VALIDATION_CSV, validation_report=VALIDATION_REPORT,
                              wf_summary=WALK_FORWARD_SUMMARY, wf_csv=WALK_FORWARD_CSV,
                              shadow_report=SHADOW_REPORT, shadow_snap=SHADOW_SNAPSHOT, shadow_perf=SHADOW_PERFORMANCE):
    """评估 4 层 Gate，返回 dict。只有全部 PASS 才是 READY_FOR_PRODUCTION（仍 ≠ ENABLED）。"""
    approval = approval if approval is not None else load_approval()
    rg, rg_reason = research_evidence_gate(validation_csv, validation_report)
    wg, wg_reason = walk_forward_gate(wf_summary, wf_csv)
    sg, sg_reason = shadow_gate(shadow_report, shadow_snap, shadow_perf)
    hg, hg_reason = human_approval_gate(approval)

    gates = {
        "research_gate": rg,
        "research_reason": rg_reason,
        "walk_forward_gate": wg,
        "walk_forward_reason": wg_reason,
        "shadow_gate": sg,
        "shadow_reason": sg_reason,
        "human_approval_gate": hg,
        "human_approval_reason": hg_reason,
    }
    all_pass = all(v == "PASS" for v in (rg, wg, sg, hg))
    gates["production_gate"] = "READY_FOR_PRODUCTION" if all_pass else "NOT_READY"
    return gates


# ============================================================================
# 8. 版本 / 状态机
# ============================================================================
def determine_state(active_model, gates, approval):
    """由当前状态推导 production state（确定性）。"""
    if QUANT_SCORE_V2_KILL_SWITCH:
        return "ROLLED_BACK" if active_model == V1_MODEL else "BLOCKED"
    if active_model == V1_MODEL:
        return "V1_ACTIVE" if not QUANT_SCORE_V2_ENABLED else "V1_ACTIVE"
    if active_model == V2_MODEL:
        if approval.get("approved") is not True:
            return "BLOCKED"
        if gates.get("production_gate") != "READY_FOR_PRODUCTION":
            return "BLOCKED"
        return "PRODUCTION_ACTIVE"
    return "NOT_ENOUGH_DATA"


def model_version_info(model_id, version, config_dict, factor_set, weights, creation_date, approval_status):
    """构造一个版本的完整信息（不覆盖旧版本）。"""
    return {
        "Model_ID": model_id,
        "Version": version,
        "Config_Hash": config_hash(config_dict),
        "Factor_Set": factor_set,
        "Weights": weights,
        "Creation_Date": creation_date,
        "Approval_Status": approval_status,
    }


# ============================================================================
# 9. Rollback
# ============================================================================
def rollback_to_v1(state):
    """V2 → V1 确定性回退。返回新 state。禁止 V1 → V2。"""
    active = state.get("active_model", V1_MODEL)
    if active == V1_MODEL:
        # V1 已是安全版本，无需回退
        return dict(state)
    new_state = dict(state)
    new_state["previous_model"] = active
    new_state["previous_version"] = state.get("active_version", "V2")
    new_state["active_model"] = V1_MODEL
    new_state["active_version"] = "V1"
    new_state["rollback_available"] = True
    new_state["last_change"] = datetime.utcnow().isoformat() + "Z"
    new_state["change_reason"] = "ROLLBACK"
    return new_state


def should_rollback(active_model, monitor_status):
    """判断是否应回退：只有 V2 且 monitor 要求 ROLLBACK_REQUIRED。"""
    return active_model == V2_MODEL and monitor_status == "ROLLBACK_REQUIRED"


# ============================================================================
# 10. Audit Trail
# ============================================================================
def audit_entry(run_date, model_id, model_version, config_hash_val, gate_status,
                approval_status, active_model, fallback_model):
    """构造一条审计记录。"""
    return {
        "schema_version": SCHEMA_VERSION,
        "Run_Date": run_date,
        "Model_ID": model_id,
        "Model_Version": model_version,
        "Config_Hash": config_hash_val,
        "Gate_Status": gate_status,
        "Approval_Status": approval_status,
        "Active_Model": active_model,
        "Fallback_Model": fallback_model,
    }


def append_audit(entry, path=AUDIT_PATH):
    """追加一条审计记录（JSONL，只追加不覆盖）。"""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


# ============================================================================
# 11. 主入口
# ============================================================================
def run_production_governance(config_path=CONFIG_PATH, approval_path=APPROVAL_PATH,
                              state_path=STATE_PATH, audit_path=AUDIT_PATH):
    """评估生产状态 → 写 state / audit → 返回状态 dict。默认 V1/disabled。"""
    cfg = load_production_config(config_path)
    approval = load_approval(approval_path)
    gates = evaluate_production_gates(approval)

    active_model = cfg.get("production_model", PRODUCTION_MODEL)
    active_version = cfg.get("version", PRODUCTION_VERSION)
    v2_enabled = bool(cfg.get("quant_score_v2_enabled", False))

    # 默认：即使 config 写了 V2，只要 ENABLED=false 就仍以 V1 运行
    if not v2_enabled:
        active_model = V1_MODEL
        active_version = "V1"

    runtime_hash = config_hash(cfg)
    approved_hash = cfg.get("config_hash")

    monitor_status, monitor_reason = safety_monitor(
        active_model, approved_hash, cfg, approval, gates)

    # 安全回退：仅 V2→V1
    if should_rollback(active_model, monitor_status):
        state = _read_json(state_path)
        state = rollback_to_v1(state if state else {"active_model": active_model, "active_version": active_version})
        active_model = V1_MODEL
        active_version = "V1"
    else:
        state = _read_json(state_path)
        if not state:
            state = {}

    state.update({
        "schema_version": SCHEMA_VERSION,
        "active_model": active_model,
        "active_version": active_version,
        "rollback_available": True,
    })
    if "previous_model" not in state:
        state["previous_model"] = None
        state["previous_version"] = None
    if "last_change" not in state:
        state["last_change"] = None
        state["change_reason"] = None

    # 写 state（原子）
    tmp = state_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, state_path)

    # 审计记录
    entry = audit_entry(
        run_date=datetime.utcnow().isoformat() + "Z",
        model_id=active_model,
        model_version=active_version,
        config_hash_val=runtime_hash,
        gate_status=gates.get("production_gate"),
        approval_status="true" if approval.get("approved") else "false",
        active_model=active_model,
        fallback_model=V1_MODEL,
    )
    append_audit(entry, audit_path)

    return {
        "active_model": active_model,
        "active_version": active_version,
        "v2_enabled": v2_enabled,
        "gates": gates,
        "monitor_status": monitor_status,
        "monitor_reason": monitor_reason,
        "production_state": determine_state(active_model, gates, approval),
        "config_hash": runtime_hash,
        # R1 一致性标志（STEP 3-C）：
        # Phase 7 无 _write_empty_outputs —— 它从不写空文件，state.json 恒含
        # V1_ACTIVE 等真实治理状态（安全默认值，必须持久存在）。
        # 因此这里不是"数据不足即不写"，而是恒为 True 以便与其它 Phase 口径一致。
        "written": True,
        "skip_empty_writes_note": (
            "Phase 7 不存在 R1 空文件风险：state.json 恒为真实治理状态（非空、非 0 行）。"
            "审计已确认无需改为 skip-write。"
        ),
    }


def main(argv=None):
    """命令行入口（STEP 3-C）：与 Phase 2 一致的 --strict 语义。

    Phase 7 恒产出真实治理状态（V1_ACTIVE 为安全默认值，必须持久），
    因此不存在"数据不足"；--strict 仅在 monitor_status 非 PASS 时返回 1。
    """
    ap = argparse.ArgumentParser(description="Quant Phase 7 · Production Governance（V1 ACTIVE，V2 DISABLED）")
    ap.add_argument("--config", default=CONFIG_PATH, help=f"production config（默认 {CONFIG_PATH}）")
    ap.add_argument("--approval", default=APPROVAL_PATH, help=f"人工审批文件（默认 {APPROVAL_PATH}）")
    ap.add_argument("--state", default=STATE_PATH, help=f"state 输出（默认 {STATE_PATH}）")
    ap.add_argument("--audit", default=AUDIT_PATH, help=f"audit JSONL（默认 {AUDIT_PATH}）")
    ap.add_argument("--strict", action="store_true",
                    help="monitor_status 非 PASS 时以退出码 1 退出（默认 0：V1 恒为安全默认）")
    args = ap.parse_args(argv)

    r = run_production_governance(config_path=args.config, approval_path=args.approval,
                                  state_path=args.state, audit_path=args.audit)
    print("[Production Governance]", json.dumps(r, ensure_ascii=False, indent=2))
    if args.strict and r.get("monitor_status") != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
