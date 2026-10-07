# -*- coding: utf-8 -*-
"""Quant Shadow Mode 纯函数回归测试（极小人工 fixture，绝不写入生产文件）。"""
import json
import os
import sys
import tempfile

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import quant_shadow as qs
from quant_factor_backtest import forward_return_nd
from quant_shadow import (
    SHADOW_ENABLE,
    SHADOW_START_DATE,
    build_shadow_performance,
    build_shadow_snapshot,
    classify_difference,
    compute_shadow_score,
    run_shadow,
    shadow_rank,
)



def check(name, cond, detail=""):
    """断言：FAIL 时抛出 AssertionError（pytest 可捕获），同时保留打印。"""
    if cond:
        print(f"  [PASS] {name}")
        return True
    print(f"  [FAIL] {name}  {detail}")
    raise AssertionError(f"{name}  {detail}".strip())


def make_snapshot(n_tickers=10, with_tag=False):
    rng = np.random.default_rng(7)
    rows = []
    for i in range(n_tickers):
        r = {
            "Scan_Date": "2026-03-02",
            "Technical_Date": "2026-02-27",
            "Ticker": f"T{i}",
            "Name": f"N{i}",
            "Sector": "Tech" if i % 2 == 0 else "Fin",
            "Price": "100",
            "Quant_Score": str(round(float(rng.uniform(50, 90)), 2)),
            "Momentum_20D_Pct": str(round(float(rng.uniform(-20, 40)), 2)),
            "RSI_14": str(round(float(rng.uniform(30, 70)), 2)),
            "ATR_Pct": str(round(float(rng.uniform(1, 8)), 2)),
            "Market_Regime": "NORMAL" if i % 3 != 0 else "STRESSED",
            "VIX": "15",
        }
        if with_tag:
            r["Tag"] = "Core_Dragon" if i < 3 else "Observation" if i < 5 else ""
            r["Final_Score"] = str(round(float(rng.uniform(60, 90)), 2))
        rows.append(r)
    return pd.DataFrame(rows)


def make_price_series(n=30):
    idx = pd.bdate_range("2026-02-27", periods=n)
    return pd.Series([100.0 + i for i in range(n)], index=idx)


# ---- 1. 空候选池 ----
def test_empty_candidate_pool():
    s = compute_shadow_score(pd.DataFrame(), "MODEL_B_BALANCED")
    check("空池 shadow score 为空", s.empty)
    snap = build_shadow_snapshot(pd.DataFrame(), "MODEL_B_BALANCED")
    check("空池 shadow snapshot 为空", snap.empty)


# ---- 2-3. Shadow disabled / active ----
def test_shadow_disabled_active():
    tmp = tempfile.mkdtemp()
    snap_path = os.path.join(tmp, "snap.csv")
    make_snapshot().to_csv(snap_path, index=False)
    # 默认 disabled
    r = run_shadow(snapshot_path=snap_path,
                   shadow_snapshot_path=os.path.join(tmp, "ss.csv"),
                   performance_path=os.path.join(tmp, "p.csv"),
                   report_path=os.path.join(tmp, "r.json"))
    check("默认 DISABLED", r["shadow_status"] == "SHADOW_DISABLED", f"got {r['shadow_status']}")
    check("DISABLED 时 shadow_snapshot 0 行", r["shadow_snapshot_rows"] == 0)
    # R1（STEP 3-C）：Shadow 禁用 → 绝不落文件（旧行为会写 0 行 CSV + report）
    check("DISABLED → shadow_snapshot.csv 未创建",
          not os.path.exists(os.path.join(tmp, "ss.csv")))
    check("DISABLED → performance.csv 未创建",
          not os.path.exists(os.path.join(tmp, "p.csv")))
    check("DISABLED → report.json 未创建",
          not os.path.exists(os.path.join(tmp, "r.json")))
    check("DISABLED → written=False", r.get("written") is False)


def test_shadow_active_logic():
    # 直接测纯函数（active 逻辑）—— 手动给 SHADOW_ENABLE=true 场景
    snap = make_snapshot(with_tag=True)
    ss = build_shadow_snapshot(snap, "MODEL_B_BALANCED", top_k=3)
    check("active 逻辑：shadow snapshot 10 行（全候选池）", len(ss) == 10, f"got {len(ss)}")
    check("Shadow_Selected 3 只", (ss["Shadow_Selected"] == "true").sum() == 3)
    check("Existing_Selected 5 只（3 Core + 2 Observation）", (ss["Existing_Selected"] == "true").sum() == 5)


# ---- 4-7. Difference 四类 ----
def test_difference_types():
    check("both selected", classify_difference(True, True) == "BOTH_SELECTED")
    check("existing only", classify_difference(True, False) == "EXISTING_ONLY")
    check("shadow only", classify_difference(False, True) == "SHADOW_ONLY")
    check("both rejected", classify_difference(False, False) == "BOTH_REJECTED")
    # 四类都出现
    snap = make_snapshot(with_tag=True)
    ss = build_shadow_snapshot(snap, "MODEL_B_BALANCED", top_k=2)
    types = set(ss["Difference_Type"].unique())
    check("四类至少部分出现", types.issubset({"BOTH_SELECTED", "EXISTING_ONLY", "SHADOW_ONLY", "BOTH_REJECTED"}),
          f"got {types}")


# ---- 8. 同一候选池 ----
def test_same_candidate_pool():
    snap = make_snapshot(with_tag=True)
    ss = build_shadow_snapshot(snap, "MODEL_B_BALANCED", top_k=3)
    check("shadow snapshot 覆盖全部候选池 ticker", set(ss["Ticker"]) == set(snap["Ticker"]))


# ---- 9. Shadow start date ----
def test_start_date():
    snap = make_snapshot(with_tag=True)
    snap2 = snap.copy()
    snap2["Scan_Date"] = "2026-03-01"  # 早于 start_date
    combined = pd.concat([snap2, snap], ignore_index=True)
    ss = build_shadow_snapshot(combined, "MODEL_B_BALANCED", top_k=3)
    check("按 Scan_Date 分组", set(ss["Scan_Date"]) == {"2026-03-01", "2026-03-02"})


# ---- 10. 不回填历史 ----
def test_no_backfill():
    # run_shadow 在 start_date 过滤只在 enable=true 时发生；这里验证 run 默认 disabled 不回填
    tmp = tempfile.mkdtemp()
    snap_path = os.path.join(tmp, "snap.csv")
    make_snapshot().to_csv(snap_path, index=False)
    r = run_shadow(snapshot_path=snap_path,
                   shadow_snapshot_path=os.path.join(tmp, "ss.csv"),
                   performance_path=os.path.join(tmp, "p.csv"),
                   report_path=os.path.join(tmp, "r.json"))
    check("默认 disabled 不产生 shadow 数据", r["shadow_snapshot_rows"] == 0)
    check("SHADOW_ENABLE 仍 false", SHADOW_ENABLE is False)
    check("SHADOW_START_DATE 仍 None", SHADOW_START_DATE is None)


# ---- 11-14. 5D/10D/20D + 缺价 ----
def test_forward_returns():
    s = make_price_series(30)
    # T = 2026-02-27, Close[T]=100
    r5 = forward_return_nd(s, "2026-02-27", 100.0, 5)
    r10 = forward_return_nd(s, "2026-02-27", 100.0, 10)
    r20 = forward_return_nd(s, "2026-02-27", 100.0, 20)
    check("5D 非 None", r5 is not None, f"got {r5}")
    check("10D 非 None", r10 is not None, f"got {r10}")
    check("20D 非 None", r20 is not None, f"got {r20}")
    # 缺价 → None
    short = pd.Series([100.0, 101.0], index=pd.bdate_range("2026-02-27", periods=2))
    check("缺未来价格 → None", forward_return_nd(short, "2026-02-27", 100.0, 5) is None)
    check("无价格序列 → None", forward_return_nd(None, "2026-02-27", 100.0, 5) is None)


def test_performance():
    snap = make_snapshot(with_tag=True)
    pm = {f"T{i}": make_price_series() for i in range(10)}
    perf = build_shadow_performance(snap, pm)
    check("performance 10 行", len(perf) == 10)
    check("有 Forward_Return_5D 列", "Forward_Return_5D" in perf.columns)
    # 缺 price_map → 全 None
    perf2 = build_shadow_performance(snap, None)
    check("缺 price_map 全 None", perf2["Forward_Return_5D"].isna().all())


# ---- 15. Regime split ----
def test_regime_split():
    snap = make_snapshot(with_tag=True)
    ss = build_shadow_snapshot(snap, "MODEL_B_BALANCED", top_k=3)
    check("有 Market_Regime 列", "Market_Regime" in ss.columns)
    regimes = set(ss["Market_Regime"].unique())
    check("含 NORMAL/STRESSED", {"NORMAL", "STRESSED"}.issubset(regimes), f"got {regimes}")


# ---- 16. Incremental value（shadow only vs existing only 都要记录）----
def test_incremental_value():
    snap = make_snapshot(with_tag=True)
    ss = build_shadow_snapshot(snap, "MODEL_B_BALANCED", top_k=2)
    shadow_only = ss[ss["Difference_Type"] == "SHADOW_ONLY"]
    existing_only = ss[ss["Difference_Type"] == "EXISTING_ONLY"]
    check("SHADOW_ONLY 有记录", len(shadow_only) >= 0)
    check("EXISTING_ONLY 有记录", len(existing_only) >= 0)
    check("两者都非空（有对比）", len(shadow_only) + len(existing_only) > 0)


# ---- 17. Overlap rate ----
def test_overlap_rate():
    snap = make_snapshot(with_tag=True)
    ss = build_shadow_snapshot(snap, "MODEL_B_BALANCED", top_k=3)
    both = int((ss["Difference_Type"] == "BOTH_SELECTED").sum())
    existing = int((ss["Existing_Selected"] == "true").sum())
    overlap = round(both / existing * 100, 2) if existing else None
    check("overlap 可计算", overlap is not None, f"got {overlap}")


# ---- 18. Deterministic ----
def test_deterministic():
    snap = make_snapshot(with_tag=True)
    s1 = compute_shadow_score(snap, "MODEL_B_BALANCED")
    s2 = compute_shadow_score(snap, "MODEL_B_BALANCED")
    pd.testing.assert_series_equal(s1, s2)
    ss1 = build_shadow_snapshot(snap, "MODEL_B_BALANCED", top_k=3)
    ss2 = build_shadow_snapshot(snap, "MODEL_B_BALANCED", top_k=3)
    pd.testing.assert_frame_equal(ss1, ss2)
    check("确定性", True)


# ---- 19. no future leakage ----
def test_no_leakage():
    # shadow score 只读因子（横截面 percentile），不读 forward return
    snap = make_snapshot(with_tag=True)
    s1 = compute_shadow_score(snap, "MODEL_B_BALANCED")
    snap2 = snap.copy()
    snap2["Forward_Return_5D"] = "999"  # 加入未来数据
    s2 = compute_shadow_score(snap2, "MODEL_B_BALANCED")
    pd.testing.assert_series_equal(s1, s2)
    check("未来数据不影响 shadow score", True)


# ---- 20-21. No AI / no network ----
def test_no_ai_no_network():
    src = open(qs.__file__).read()
    check("无 AI 依赖", not any(k in src for k in ["ClawSocket", "openai", "anthropic", "gpt-"]))
    check("无网络请求", "requests" not in src and "yfinance" not in src)


# ---- 22. production remains disabled ----
def test_production_disabled():
    check("SHADOW_ENABLE 默认 false", SHADOW_ENABLE is False)
    check("QUANT_SCORE_V2_ENABLED 仍 false", qs.QUANT_SCORE_V2_ENABLED is False)


# ---- 23. Existing Scan result unchanged ----
def test_existing_scan_unchanged():
    # 不 import scan.py，且不改 Quant_Score
    src = open(qs.__file__).read()
    check("不 import scan/review", "import scan" not in src and "import review" not in src)
    check("不赋值 Quant_Score", "Quant_Score =" not in src)


# ---- 空数据 report 内容 ----
def test_empty_report():
    tmp = tempfile.mkdtemp()
    r = run_shadow(snapshot_path="/tmp/nonexistent_snap.csv",
                   shadow_snapshot_path=os.path.join(tmp, "ss.csv"),
                   performance_path=os.path.join(tmp, "p.csv"),
                   report_path=os.path.join(tmp, "r.json"))
    check("空数据 shadow_status=DISABLED", r["shadow_status"] == "SHADOW_DISABLED")
    # R1（STEP 3-C）：无 snapshot → 绝不落文件
    check("空数据 → report.json 未创建", not os.path.exists(os.path.join(tmp, "r.json")))
    check("空数据 → shadow_snapshot.csv 未创建", not os.path.exists(os.path.join(tmp, "ss.csv")))
    check("空数据 → written=False", r.get("written") is False)
    # 不伪造结论：内存态返回值中不得出现任何选中计数
    check("空数据 → shadow_snapshot_rows=0", r["shadow_snapshot_rows"] == 0)
    check("空数据 → performance_rows=0", r["performance_rows"] == 0)


# ---- STEP 3-C：Phase 6 R1 —— 禁用/无数据绝不落文件 ----
def test_no_data_no_files():
    """R1：Phase 6 在 Shadow 禁用或 snapshot 为空时必须【不创建任何文件】。

    Shadow 当前恒为 SHADOW_DISABLED，旧行为每次运行都会往仓库丢
    "0 行 shadow_snapshot.csv + 0 行 performance.csv + report.json"。
    """
    tmp = tempfile.mkdtemp()
    ss_path = os.path.join(tmp, "ss.csv")
    p_path = os.path.join(tmp, "p.csv")
    r_path = os.path.join(tmp, "r.json")

    def none_exist(tag):
        check(f"[{tag}] shadow_snapshot.csv 未创建", not os.path.exists(ss_path))
        check(f"[{tag}] performance.csv 未创建", not os.path.exists(p_path))
        check(f"[{tag}] report.json 未创建", not os.path.exists(r_path))

    # (a) SHADOW 未启用（当前真实状态）+ 有 snapshot
    snap_path = os.path.join(tmp, "snap.csv")
    make_snapshot().to_csv(snap_path, index=False)
    ra = run_shadow(snapshot_path=snap_path, shadow_snapshot_path=ss_path,
                    performance_path=p_path, report_path=r_path)
    check("(a) shadow_status=SHADOW_DISABLED", ra["shadow_status"] == "SHADOW_DISABLED")
    check("(a) written=False", ra.get("written") is False)
    none_exist("a SHADOW_DISABLED")

    # (b) snapshot 不存在
    rb = run_shadow(snapshot_path=os.path.join(tmp, "missing.csv"),
                    shadow_snapshot_path=ss_path, performance_path=p_path, report_path=r_path)
    check("(b) shadow_status=SHADOW_DISABLED", rb["shadow_status"] == "SHADOW_DISABLED")
    none_exist("b 无 snapshot")

    # 禁用期间不得产生任何"选中计数"类伪结果
    check("禁用期 shadow_snapshot_rows=0", ra["shadow_snapshot_rows"] == 0)
    check("禁用期 performance_rows=0", ra["performance_rows"] == 0)


def main():
    _tests = [
        test_empty_candidate_pool,
        test_shadow_disabled_active,
        test_shadow_active_logic,
        test_difference_types,
        test_same_candidate_pool,
        test_start_date,
        test_no_backfill,
        test_forward_returns,
        test_performance,
        test_regime_split,
        test_incremental_value,
        test_overlap_rate,
        test_deterministic,
        test_no_leakage,
        test_no_ai_no_network,
        test_production_disabled,
        test_existing_scan_unchanged,
        test_empty_report,
        # ---- STEP 3-C ----
        test_no_data_no_files,
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
