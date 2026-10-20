#!/usr/bin/env python3
"""Quant Research Runner — Phase 2–7 生产编排器。

串联并执行量化研究 Phase 2→7，实现：
  · 严格依赖顺序（2 回测 → 3 验证 → 4 评分 → 5 Walk-Forward → 6 Shadow → 7 生产治理）
  · 每步前置检查（输入文件存在 / 非空 / schema_version 匹配）；缺失则降级为 NOT_ENOUGH_DATA，不落空文件（R1）
  · 失败隔离（单 Phase 异常不阻断其余 Phase，记入状态）
  · 输出各 Phase 结果到既有约定文件名，并写 quant_research_status.json 汇总

本文件只做编排与接线，不修改任何 Phase 2–7 的核心业务逻辑、数据源、Gate 或列定义。
各 Phase 通过延迟导入其 run_* 函数执行；所有 run_* 均有完整默认参数，默认读写仓库根目录的约定文件名。

CLI:
    python quant_research_runner.py                  # 跑全部 Phase
    python quant_research_runner.py --strict         # 任一 Phase 未就绪/失败 → 退出码 1
    python quant_research_runner.py --phase 5        # 只跑指定 Phase
    python quant_research_runner.py --workdir DIR    # 在 DIR 内读写（默认当前目录）
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Phase 规格表（仅声明，不在导入时加载任何 Phase 模块）
# inputs: [(文件名, 期望 schema_version)]；schema_version=None 表示不校验
# 注意：Phase 4 模块为 quant_score_v2.py（文件名不含 "factor"）
# ---------------------------------------------------------------------------
PHASE_SPECS = [
    {
        "num": 2, "name": "backtest",
        "module": "quant_factor_backtest", "func": "run_backtest_from_history",
        "inputs": [("quant_factor_snapshot.csv", "phase1.v1"),
                   ("quant_factor_price_history.csv", "phase2b.v1")],
    },
    {
        "num": 3, "name": "validation",
        "module": "quant_factor_validation", "func": "run_validation",
        "inputs": [("quant_factor_backtest.csv", "phase2.v1")],
    },
    {
        "num": 4, "name": "score_v2",
        "module": "quant_score_v2", "func": "run_quant_score_v2",
        "inputs": [("quant_factor_validation.csv", "phase3.v1"),
                   ("quant_factor_correlation.csv", "phase3.v1")],
    },
    {
        "num": 5, "name": "walk_forward",
        "module": "quant_walk_forward", "func": "run_walk_forward",
        "inputs": [("quant_factor_backtest.csv", "phase2.v1")],
    },
    {
        "num": 6, "name": "shadow",
        "module": "quant_shadow", "func": "run_shadow",
        "inputs": [("quant_factor_snapshot.csv", "phase1.v1")],
    },
    {
        "num": 7, "name": "production",
        "module": "quant_production", "func": "run_production_governance",
        "inputs": [],
    },
]

# 测试可注入的 Phase 函数覆盖（num -> callable() -> result dict）。
# 默认空：运行时延迟导入真实模块。设置后仅用于隔离测试，不触碰任何 Phase 核心逻辑。
PHASE_FUNCS = {}


def _read_schema_version(path):
    """读取 CSV 最后一行的 schema_version（用于前置匹配校验）。读取失败返回 None。"""
    try:
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return None
        import csv
        with open(path, "r", encoding="utf-8", newline="") as fh:
            reader = csv.reader(fh)
            header = next(reader, [])
            if "schema_version" not in header:
                return None
            idx = header.index("schema_version")
            last = None
            for row in reader:
                if len(row) > idx:
                    val = (row[idx] or "").strip()
                    if val:
                        last = val
            return last
    except Exception:
        return None


def _precheck(spec, workdir):
    """返回 (ok, reason, schema_warnings)。ok=False 时该 Phase 应降级跳过（不调用 run_*）。"""
    warnings = []
    for fname, expected in spec.get("inputs", []):
        fpath = os.path.join(workdir, fname)
        if not os.path.exists(fpath) or os.path.getsize(fpath) == 0:
            return False, "输入缺失或为空: %s" % fname, warnings
        if expected is not None:
            actual = _read_schema_version(fpath)
            if actual is not None and actual != expected:
                warnings.append("%s schema_version=%s 期望 %s" % (fname, actual, expected))
    return True, None, warnings


def _invoke(spec):
    """延迟导入真实 Phase 模块并执行其 run_*（全部默认参数，读写 workdir 内约定文件名）。"""
    mod = importlib.import_module(spec["module"])
    fn = getattr(mod, spec["func"])
    return fn()


def run_phase(spec, workdir):
    """执行单个 Phase，返回结果 dict（含 name/status/written/reason/schema_warnings/_error）。"""
    result = {
        "name": spec["name"],
        "status": "NOT_ENOUGH_DATA",
        "written": False,
        "reason": None,
        "schema_warnings": [],
        "_error": None,
    }
    ok, reason, warnings = _precheck(spec, workdir)
    result["schema_warnings"] = warnings
    if not ok:
        result["reason"] = reason
        result["status"] = "NOT_ENOUGH_DATA"
        return result
    try:
        if spec["num"] in PHASE_FUNCS:
            out = PHASE_FUNCS[spec["num"]]()
        else:
            out = _invoke(spec)
        if isinstance(out, dict):
            result["status"] = out.get("status", "OK")
            result["written"] = bool(out.get("written", False))
            if out.get("reason"):
                result["reason"] = out.get("reason")
        else:
            result["status"] = "OK"
    except Exception as exc:  # 失败隔离：单 Phase 异常不阻断其余
        result["_error"] = "%s: %s" % (type(exc).__name__, exc)
        result["status"] = "ERROR"
        result["reason"] = "异常: %s" % result["_error"]
    return result


def run(workdir=".", strict=False, only_phase=None,
        status_json="quant_research_status.json"):
    """执行编排。返回 (summary_dict, exit_code)。"""
    specs = [s for s in PHASE_SPECS if only_phase is None or s["num"] == only_phase]
    prev_cwd = os.getcwd()
    phases_out = {}
    try:
        os.chdir(workdir)
        for spec in specs:
            res = run_phase(spec, workdir)
            phases_out[spec["num"]] = res
            tag = res["status"]
            err = ("  <- " + res["_error"]) if res["_error"] else ""
            warn = ("  [schema警告: %s]" % "; ".join(res["schema_warnings"])) if res["schema_warnings"] else ""
            print("[Phase %d %s] status=%s%s%s" % (spec["num"], spec["name"], tag, warn, err), flush=True)
    finally:
        os.chdir(prev_cwd)

    any_error = any(r.get("_error") for r in phases_out.values())
    any_not_ok = any(r["status"] != "OK" for r in phases_out.values())
    overall = "FAILED" if any_error else ("DEGRADED" if any_not_ok else "OK")

    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "workdir": os.path.abspath(workdir),
        "strict": bool(strict),
        "only_phase": only_phase,
        "overall_status": overall,
        "phases": {str(n): {"name": r["name"], "status": r["status"],
                            "written": r["written"], "reason": r["reason"],
                            "schema_warnings": r["schema_warnings"],
                            "_error": r["_error"]}
                   for n, r in sorted(phases_out.items())},
    }
    out_path = os.path.join(workdir, status_json) if not os.path.isabs(status_json) else status_json
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print("[Runner] overall_status=%s -> %s" % (overall, out_path), flush=True)

    exit_code = 0
    if strict and (any_error or any_not_ok):
        exit_code = 1
    return summary, exit_code


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Quant Phase 2-7 研究编排器（只读消费既有产物，R1：无数据不落空文件）")
    ap.add_argument("--workdir", default=".", help="读写目录（默认当前目录）")
    ap.add_argument("--strict", action="store_true",
                    help="任一 Phase 未就绪(非OK)/异常 -> 退出码 1（默认 0：数据未就绪是预期状态）")
    ap.add_argument("--phase", type=int, default=None, choices=[2, 3, 4, 5, 6, 7],
                    help="只跑指定 Phase（2-7）")
    ap.add_argument("--status-json", default="quant_research_status.json",
                    help="汇总输出 JSON 路径（默认 quant_research_status.json）")
    args = ap.parse_args(argv)
    _, code = run(workdir=args.workdir, strict=args.strict,
                  only_phase=args.phase, status_json=args.status_json)
    return code


if __name__ == "__main__":
    sys.exit(main())
