"""quant_research_runner 的编排逻辑测试。

通过注入 PHASE_FUNCS 覆盖（stub）真实 Phase 模块，使测试：
  · 不依赖真实行情/因子数据（不硬编码绝对日期）
  · 不导入重型 Phase 模块（快速、确定）
  · 聚焦验证编排本身：顺序、前置降级(R1)、失败隔离、--strict、--phase、幂等

真实 Phase 代码的端到端执行由各模块自身测试 + CI 中 quant-research.yml 工作流覆盖。
"""
import json
import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import quant_research_runner as runner  # noqa: E402


@pytest.fixture
def workdir():
    d = tempfile.mkdtemp(prefix="qr_runner_")
    yield d


def _override(phases):
    """phases: {num: status} -> 构造 stub 覆盖 PHASE_FUNCS（written 仅当 status=='OK'）。"""
    funcs = {}
    for num, st in phases.items():
        funcs[num] = (lambda st=st: {"status": st, "written": st == "OK", "reason": None})
    runner.PHASE_FUNCS = funcs


def _clear_override():
    runner.PHASE_FUNCS = {}


def _seed_inputs(workdir):
    """写入最小占位输入文件（正确的 schema_version 末行），使前置检查通过、PHASE_FUNCS 覆盖生效。

    不写入任何真实行情，仅是满足 schema 的占位行。runner 前置检查在 PHASE_FUNCS
    覆盖之前执行，缺少输入会直接降级 NOT_ENOUGH_DATA 而不调用覆盖函数，故测试需先播种。
    仅用于隔离测试，不触碰任何 Phase 核心逻辑。
    """
    files = {
        "quant_factor_snapshot.csv": "phase1.v1",
        "quant_factor_price_history.csv": "phase2b.v1",
        "quant_factor_backtest.csv": "phase2.v1",
        "quant_factor_validation.csv": "phase3.v1",
        "quant_factor_correlation.csv": "phase3.v1",
    }
    for name, sv in files.items():
        with open(os.path.join(workdir, name), "w", encoding="utf-8", newline="") as fh:
            fh.write("schema_version\n")
            fh.write("%s\n" % sv)


def _data_files_present(workdir):
    names = [
        "quant_factor_backtest.csv", "quant_factor_validation.csv",
        "quant_factor_correlation.csv", "quant_factor_registry.csv",
        "quant_factor_clusters.csv", "quant_score_v2_candidates.csv",
        "quant_walk_forward_results.csv", "quant_walk_forward_summary.json",
        "quant_shadow_performance.csv", "quant_shadow_snapshot.csv",
        "quant_production_state.json", "quant_production_audit.jsonl",
    ]
    return [f for f in names if os.path.exists(os.path.join(workdir, f))]


def test_full_pipeline_ok(workdir):
    _seed_inputs(workdir)
    _override({2: "OK", 3: "OK", 4: "OK", 5: "OK", 6: "OK", 7: "OK"})
    try:
        summary, code = runner.run(workdir=workdir, strict=False)
    finally:
        _clear_override()
    assert code == 0
    assert summary["overall_status"] == "OK"
    assert set(summary["phases"].keys()) == {"2", "3", "4", "5", "6", "7"}
    for p in summary["phases"].values():
        assert p["status"] == "OK"


def test_missing_input_degrades_no_file(workdir):
    # 仅覆盖 Phase 7（无输入，否则会真实导入模块并写治理文件）。
    # Phase 2-6 走真实前置检查 -> 输入缺失 -> 跳过（不调用 run_*，不落数据文件）。
    _override({7: "NOT_ENOUGH_DATA"})
    try:
        summary, code = runner.run(workdir=workdir, strict=False)
    finally:
        _clear_override()
    for n in ("2", "3", "4", "5", "6"):
        assert summary["phases"][n]["status"] == "NOT_ENOUGH_DATA"
        assert summary["phases"][n]["written"] is False
    # R1：不得创建任何数据产物（status json 由 runner 负责，不在此列）
    assert _data_files_present(workdir) == [], "不应创建数据文件"
    # 非 strict 下，数据未就绪是预期状态 -> 退出码 0
    assert code == 0


def test_single_phase_failure_isolated(workdir):
    _seed_inputs(workdir)

    def boom():
        raise RuntimeError("simulated phase failure")

    runner.PHASE_FUNCS = {
        2: boom,
        3: lambda: {"status": "OK", "written": True},
        4: lambda: {"status": "OK", "written": True},
        5: lambda: {"status": "OK", "written": True},
        6: lambda: {"status": "OK", "written": True},
        7: lambda: {"status": "OK", "written": True},
    }
    try:
        summary, code = runner.run(workdir=workdir, strict=False)
    finally:
        _clear_override()
    assert summary["phases"]["2"]["status"] == "ERROR"
    assert summary["phases"]["2"]["_error"] is not None
    for n in ("3", "4", "5", "6", "7"):
        assert summary["phases"][n]["status"] == "OK"
    # 失败隔离：非 strict 下仍退出 0
    assert code == 0


def test_strict_exit_code(workdir):
    _override({2: "NOT_ENOUGH_DATA", 3: "OK", 4: "OK", 5: "OK", 6: "OK", 7: "OK"})
    try:
        _, code_nonstrict = runner.run(workdir=workdir, strict=False)
        _, code_strict = runner.run(workdir=workdir, strict=True)
    finally:
        _clear_override()
    assert code_nonstrict == 0
    # strict 下 NOT_ENOUGH_DATA 视为未就绪 -> 退出码非 0
    assert code_strict == 1


def test_phase_filter(workdir):
    _seed_inputs(workdir)
    _override({2: "OK", 3: "OK", 4: "OK", 5: "OK", 6: "OK", 7: "OK"})
    try:
        summary, code = runner.run(workdir=workdir, strict=False, only_phase=5)
    finally:
        _clear_override()
    assert set(summary["phases"].keys()) == {"5"}
    assert summary["phases"]["5"]["status"] == "OK"
    assert code == 0


def test_idempotency(workdir):
    _override({2: "OK", 3: "OK", 4: "OK", 5: "OK", 6: "OK", 7: "OK"})
    try:
        s1, _ = runner.run(workdir=workdir, strict=False)
        s2, _ = runner.run(workdir=workdir, strict=False)
    finally:
        _clear_override()
    p1 = {k: v["status"] for k, v in s1["phases"].items()}
    p2 = {k: v["status"] for k, v in s2["phases"].items()}
    assert p1 == p2
    # 两次汇总（除 run_at 时间戳）应一致
    j1 = {k: v for k, v in s1.items() if k != "run_at"}
    j2 = {k: v for k, v in s2.items() if k != "run_at"}
    assert j1 == j2
    assert os.path.exists(os.path.join(workdir, "quant_research_status.json"))
