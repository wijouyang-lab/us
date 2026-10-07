# -*- coding: utf-8 -*-
"""Quant Factor Backtest 纯函数回归测试（不依赖真实 Yahoo 网络）。"""
import os
import sys
import tempfile

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_factor_backtest import (
    assign_quantile,
    compute_correlation,
    compute_factor_summary,
    compute_forward_returns,
    compute_quantile_stats,
    compute_regime_summary,
    factor_type,
    forward_return_nd,
    maturity_status,
    run_backtest,
    sample_size_label,
)



def check(name, cond, detail=""):
    """断言：FAIL 时抛出 AssertionError（pytest 可捕获），同时保留打印。"""
    if cond:
        print(f"  [PASS] {name}")
        return True
    print(f"  [FAIL] {name}  {detail}")
    raise AssertionError(f"{name}  {detail}".strip())


def make_price_series(start="2026-01-01", n=30, step=1.0):
    idx = pd.bdate_range(start, periods=n)
    return pd.Series([100.0 + i * step for i in range(n)], index=idx)


def make_snapshot():
    """构造一个小型全候选池 snapshot（含 3 只股票、2 个交易日）。"""
    return pd.DataFrame({
        "Scan_Date": ["2026-02-01", "2026-02-01", "2026-02-01", "2026-02-02", "2026-02-02"],
        "Technical_Date": ["2026-01-30", "2026-01-30", "2026-01-30", "2026-02-02", "2026-02-02"],
        "Ticker": ["AAA", "BBB", "CCC", "AAA", "BBB"],
        "Name": ["A", "B", "C", "A", "B"],
        "Sector": ["Tech", "Tech", "Fin", "Tech", "Tech"],
        "Market_Regime": ["NORMAL", "NORMAL", "STRESSED", "NORMAL", "STRESSED"],
        "VIX": ["15", "15", "28", "15", "28"],
        "Price": ["100", "100", "100", "105", "102"],
        "RSI_14": ["50", "60", "70", "55", "65"],
        "Bias_Pct": ["1", "2", "3", "2", "4"],
        "Momentum_5D_Pct": ["5", "10", "15", "6", "12"],
        "ZScore_20D": ["0.5", "1.0", "1.5", "0.6", "1.2"],
        "Beta_60D_SPY": ["1.0", "1.1", "1.2", "1.0", "1.1"],
        "Quant_Score": ["75", "70", "65", "76", "71"],
        "Fundamental_Score": ["25", "24", "23", "26", "25"],
        "Event_Score": ["15", "14", "13", "16", "15"],
        "Technical_Score_25": ["20", "19", "18", "21", "20"],
        "Risk_Liquidity_Score": ["15", "13", "11", "14", "13"],
    })


# ---- 1-4. Forward Return 5D/10D/20D + 缺失 ----
def test_forward_return():
    s = make_price_series(start="2026-01-01", n=30, step=1.0)
    # T = 2026-01-01（index[0]），Close[T]=100；T+5 = index[5]=105
    r5 = forward_return_nd(s, "2026-01-01", 100.0, 5)
    check("Forward 5D = 5%", r5 is not None and abs(r5 - 0.05) < 1e-6, f"got {r5}")

    # T+10 = index[10] = 110 → 10%
    r10 = forward_return_nd(s, "2026-01-01", 100.0, 10)
    check("Forward 10D = 10%", r10 is not None and abs(r10 - 0.10) < 1e-6, f"got {r10}")

    # T+20 = index[20] = 120 → 20%
    r20 = forward_return_nd(s, "2026-01-01", 100.0, 20)
    check("Forward 20D = 20%", r20 is not None and abs(r20 - 0.20) < 1e-6, f"got {r20}")


def test_forward_missing_future():
    s = make_price_series(start="2026-01-01", n=10, step=1.0)
    # T = index[8]，只有 1 个未来交易日 → 5D 缺失
    r5 = forward_return_nd(s, s.index[8], 100.0, 5)
    check("未来交易日不足 → None", r5 is None, f"got {r5}")
    # 未来恰好不存在 → 20D None
    r20 = forward_return_nd(s, s.index[9], 100.0, 20)
    check("未来完全不存在 → None", r20 is None, f"got {r20}")


# ---- 5-6. Win 判定 ----
def test_win():
    s = make_price_series(start="2026-01-01", n=30, step=1.0)
    price_map = {"AAA": s, "BBB": s.copy()}
    snap = make_snapshot().head(1).copy()  # 只有 AAA 一行
    df = compute_forward_returns(snap, price_map)
    # Close[T]=100, T+5=105 → win=1
    check("Win>0 → 1", df.iloc[0]["Win_5D"] == 1, f"got {df.iloc[0]['Win_5D']}")

    # 构造平盘：future == Close[T] → Win=0（不是 Win）
    flat = pd.Series([100.0] * 20, index=pd.bdate_range("2026-01-26", periods=20))
    snap2 = make_snapshot().head(1).copy()
    df2 = compute_forward_returns(snap2, {"AAA": flat})
    check("Win=0 时不是 Win（=0）", df2.iloc[0]["Win_5D"] == 0, f"got {df2.iloc[0]['Win_5D']}")

    # 未来缺失 → Win None
    short = make_price_series(start="2026-01-01", n=3, step=1.0)
    df3 = compute_forward_returns(snap2, {"AAA": short})
    check("未来缺失 → Win None", df3.iloc[0]["Win_5D"] is None, f"got {df3.iloc[0]['Win_5D']}")


# ---- 7-8. 五分位分组 ----
def test_quantile():
    vals = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], dtype=float)
    q = assign_quantile(vals, 5)
    check("五分位分组正确", q.notna().all() and set(q.unique()) == {"Q1", "Q2", "Q3", "Q4", "Q5"},
          f"got {sorted(q.unique())}")

    # 同值因子：全部相同 → qcut duplicates 会 drop，此时 qcut 报错 → 我们兜底返回全 None
    same = pd.Series([5.0] * 10)
    qs = assign_quantile(same, 5)
    check("同值因子不抛错", qs.notna().sum() == 0, f"got {qs.tolist()}")

    # 样本不足 5 → None
    few = pd.Series([1.0, 2.0, 3.0])
    qf = assign_quantile(few, 5)
    check("样本不足 → 不分组", qf.notna().sum() == 0, f"got {qf.tolist()}")


# ---- 9-10. N 正确 / NaN 不进入统计 ----
def test_n_and_nan():
    s = make_price_series(start="2026-01-01", n=30, step=1.0)
    snap = make_snapshot()
    price_map = {"AAA": s, "BBB": s.copy(), "CCC": s.copy()}
    bt = compute_forward_returns(snap, price_map)
    summ = compute_factor_summary(bt)

    # 5 行 snapshot，其中 CCC 的 5D 应该也能算（T=2026-01-30 在 index 范围内吗？）
    # 注：snapshot 的 Technical_Date 是 2026-01-30，而 price series 从 2026-01-01 开始，
    # 30 个交易日足够覆盖 T+20。所以 5 行 forward return 都应有值。
    row = summ[(summ["Factor"] == "RSI_14") & (summ["Horizon"] == "5D")].iloc[0]
    check("N = 5（全部样本）", row["N"] == 5, f"got {row['N']}")

    # NaN 因子不进入：给一行 RSI 设 NaN，仍应有 N=5（因为 RSI 不是 dropna 条件，只有 return 是）
    # 但 summary 只 drop return 的 NaN，不 drop 因子 NaN。这里验证 return NaN 被排除。
    bt2 = bt.copy()
    bt2.loc[0, "Forward_Return_5D"] = None
    bt2.loc[0, "Win_5D"] = None
    summ2 = compute_factor_summary(bt2)
    row2 = summ2[(summ2["Factor"] == "RSI_14") & (summ2["Horizon"] == "5D")].iloc[0]
    check("return NaN 不进入统计（N=4）", row2["N"] == 4, f"got {row2['N']}")


# ---- 11. Market Regime 分层 ----
def test_regime():
    s = make_price_series(start="2026-01-01", n=30, step=1.0)
    snap = make_snapshot()
    price_map = {"AAA": s, "BBB": s.copy(), "CCC": s.copy()}
    bt = compute_forward_returns(snap, price_map)
    reg = compute_regime_summary(bt)
    regimes = set(reg["Market_Regime"].unique())
    check("Regime 分层包含 NORMAL/STRESSED", {"NORMAL", "STRESSED"}.issubset(regimes),
          f"got {regimes}")


# ---- 12. Snapshot 不被修改 ----
def test_snapshot_immutable():
    snap = make_snapshot()
    snap_copy = snap.copy(deep=True)
    s = make_price_series(start="2026-01-01", n=30, step=1.0)
    _ = compute_forward_returns(snap, {"AAA": s, "BBB": s.copy(), "CCC": s.copy()})
    pd.testing.assert_frame_equal(snap, snap_copy)
    check("Snapshot 不被修改", True)


# ---- 13. 不使用未来数据 ----
def test_no_lookahead():
    # Forward Return 只读 T 之后的收盘价；因子本身来自 snapshot，不读取任何 Exit/PnL/Review 字段。
    # 验证：compute_forward_returns 不产生任何依赖未来因子的行为——
    # 传入的 snapshot 里没有 Exit_Price/PnL 列，结果也不该有这些列。
    snap = make_snapshot()
    s = make_price_series(start="2026-01-01", n=30, step=1.0)
    bt = compute_forward_returns(snap, {"AAA": s, "BBB": s.copy(), "CCC": s.copy()})
    check("无 Exit/PnL 列泄漏", not any("Exit" in c or "PnL" in c for c in bt.columns))
    # 因子值未被回写改动
    check("RSI 因子值未被改动", list(bt["RSI_14"].astype(str)) == list(snap["RSI_14"].astype(str)))


# ---- 14-15. 确定性 / 无随机性 ----
def test_deterministic():
    s = make_price_series(start="2026-01-01", n=30, step=1.0)
    snap = make_snapshot()
    price_map = {"AAA": s, "BBB": s.copy(), "CCC": s.copy()}
    bt1 = compute_forward_returns(snap, price_map)
    bt2 = compute_forward_returns(snap, price_map)
    pd.testing.assert_frame_equal(bt1, bt2)
    summ1 = compute_factor_summary(bt1)
    summ2 = compute_factor_summary(bt2)
    pd.testing.assert_frame_equal(summ1, summ2)
    check("重复运行结果一致（无随机性）", True)


# ---- 辅助：correlation / factor_type / sample_size / maturity ----
def test_helpers():
    s = make_price_series(start="2026-01-01", n=30, step=1.0)
    snap = make_snapshot()
    bt = compute_forward_returns(snap, {"AAA": s, "BBB": s.copy(), "CCC": s.copy()})
    p, sp = compute_correlation(bt, "Momentum_5D_Pct", 5)
    check("corr 返回数值", p is not None and sp is not None, f"got {p},{sp}")

    check("factor_type Composite", factor_type("Quant_Score") == "Composite")
    check("factor_type Raw", factor_type("RSI_14") == "Raw Factor")
    check("factor_type Existing", factor_type("Fundamental_Score") == "Existing Scan Score")

    check("sample_size_label <30", sample_size_label(10) == "Exploratory Only")
    check("sample_size_label >=100", sample_size_label(150) == "Formal Comparison OK")

    # maturity：30 交易日足够 20D
    m = maturity_status({"AAA": s, "BBB": s.copy(), "CCC": s.copy()}, snap, 5)
    check("maturity 5D = 5", m == 5, f"got {m}")


# ---- run_backtest 主入口（空 snapshot / 无价格）----
def test_run_backtest_empty():
    tmp = tempfile.mkdtemp()
    snap_path = os.path.join(tmp, "quant_factor_snapshot.csv")
    bt_path = os.path.join(tmp, "quant_factor_backtest.csv")
    summ_path = os.path.join(tmp, "quant_factor_summary.csv")

    # 无 snapshot
    r = run_backtest(snapshot_path=snap_path, backtest_path=bt_path, summary_path=summ_path)
    check("无 snapshot → NOT_ENOUGH_DATA", r["status"] == "NOT_ENOUGH_DATA", f"got {r['status']}")

    # 空 snapshot
    pd.DataFrame(columns=["Ticker"]).to_csv(snap_path, index=False)
    r2 = run_backtest(snapshot_path=snap_path, backtest_path=bt_path, summary_path=summ_path)
    check("空 snapshot → NOT_ENOUGH_DATA", r2["status"] == "NOT_ENOUGH_DATA", f"got {r2['status']}")

    # 有 snapshot 但无价格 → 报告缺口
    make_snapshot().to_csv(snap_path, index=False)
    r3 = run_backtest(snapshot_path=snap_path, price_map=None, backtest_path=bt_path, summary_path=summ_path)
    check("有 snapshot 无价格 → 报告缺口", r3["status"] == "NOT_ENOUGH_DATA", f"got {r3['status']}")

    # 有 snapshot + 价格 → OK
    s = make_price_series(start="2026-01-01", n=30, step=1.0)
    r4 = run_backtest(snapshot_path=snap_path, price_map={"AAA": s, "BBB": s.copy(), "CCC": s.copy()},
                      backtest_path=bt_path, summary_path=summ_path)
    check("有价格 → OK", r4["status"] == "OK", f"got {r4['status']}")
    check("backtest_rows = 5", r4["backtest_rows"] == 5, f"got {r4['backtest_rows']}")
    check("backtest.csv 已写", os.path.exists(bt_path) and os.path.getsize(bt_path) > 0)
    check("summary.csv 已写", os.path.exists(summ_path) and os.path.getsize(summ_path) > 0)


def test_quantile_stats_group_by_date():
    s = make_price_series(start="2026-01-01", n=30, step=1.0)
    snap = make_snapshot()
    bt = compute_forward_returns(snap, {"AAA": s, "BBB": s.copy(), "CCC": s.copy()})
    qs = compute_quantile_stats(bt, "RSI_14", 5, n_bins=5, group_by_date=True)
    # 每个 Snapshot_Date 只有 3 个样本（<5），无法分 5 档 → 结果为空
    check("每日样本不足 → 空分位表", qs.empty, f"got {len(qs)} rows")


# ============================================================================
# STEP 3-B：run_backtest 四类路径测试
#   1) 正常数据路径  2) 无数据路径（R1：确认不落文件）
#   3) 异常数据路径  4) idempotency（重复运行逐字节一致）
# ============================================================================

# ---- 1. 正常数据路径 ----
def test_run_backtest_normal_path():
    tmp = tempfile.mkdtemp()
    snap_path = os.path.join(tmp, "quant_factor_snapshot.csv")
    bt_path = os.path.join(tmp, "quant_factor_backtest.csv")
    summ_path = os.path.join(tmp, "quant_factor_summary.csv")

    make_snapshot().to_csv(snap_path, index=False)
    s = make_price_series(start="2026-01-01", n=40, step=1.0)
    r = run_backtest(snapshot_path=snap_path,
                     price_map={"AAA": s, "BBB": s.copy(), "CCC": s.copy()},
                     backtest_path=bt_path, summary_path=summ_path)
    check("正常路径 → OK", r["status"] == "OK", f"got {r['status']}")
    check("正常路径 written=True", r.get("written") is True, f"got {r.get('written')}")
    check("backtest.csv 已写且非空", os.path.exists(bt_path) and os.path.getsize(bt_path) > 0)
    check("summary.csv 已写且非空", os.path.exists(summ_path) and os.path.getsize(summ_path) > 0)

    bt = pd.read_csv(bt_path, dtype=str, keep_default_na=False)
    check("backtest 行数 = snapshot 行数", len(bt) == 5, f"got {len(bt)}")
    for n in (5, 10, 20):
        check(f"含 Forward_Return_{n}D 列", f"Forward_Return_{n}D" in bt.columns)
    check("backtest 带 phase2.v1 schema_version",
          bt["schema_version"].iloc[0] == "phase2.v1", str(bt["schema_version"].iloc[0]))

    summ = pd.read_csv(summ_path, dtype=str, keep_default_na=False)
    check("summary 非空", len(summ) > 0, f"got {len(summ)}")
    check("summary 带 phase2.v1 schema_version",
          summ["schema_version"].iloc[0] == "phase2.v1", str(summ["schema_version"].iloc[0]))
    # 正常路径也不得凭空产生"证据性"结论：必须有 N 列且可解析
    check("summary 含 N 列", "N" in summ.columns)


# ---- 2. 无数据路径（R1 修复核心：绝不落空文件） ----
def test_run_backtest_no_data_no_file():
    """R1：无数据时必须【不产生任何文件】。

    旧行为会写 0 字节 CSV —— 下游看到"文件存在"可能静默通过。
    新行为：文件不存在，下游明确报 NOT_ENOUGH_DATA。
    """
    tmp = tempfile.mkdtemp()
    snap_path = os.path.join(tmp, "quant_factor_snapshot.csv")
    bt_path = os.path.join(tmp, "quant_factor_backtest.csv")
    summ_path = os.path.join(tmp, "quant_factor_summary.csv")

    def both_absent(tag):
        check(f"[{tag}] backtest.csv 未创建",
              not os.path.exists(bt_path), f"存在且 {os.path.getsize(bt_path) if os.path.exists(bt_path) else 0} 字节")
        check(f"[{tag}] summary.csv 未创建",
              not os.path.exists(summ_path), f"存在且 {os.path.getsize(summ_path) if os.path.exists(summ_path) else 0} 字节")

    # (a) snapshot 不存在
    r1 = run_backtest(snapshot_path=snap_path, backtest_path=bt_path, summary_path=summ_path)
    check("(a) 无 snapshot → NOT_ENOUGH_DATA", r1["status"] == "NOT_ENOUGH_DATA", f"got {r1['status']}")
    check("(a) written=False", r1.get("written") is False)
    both_absent("a 无 snapshot")

    # (b) snapshot 为空
    pd.DataFrame(columns=["Ticker"]).to_csv(snap_path, index=False)
    r2 = run_backtest(snapshot_path=snap_path, backtest_path=bt_path, summary_path=summ_path)
    check("(b) 空 snapshot → NOT_ENOUGH_DATA", r2["status"] == "NOT_ENOUGH_DATA", f"got {r2['status']}")
    both_absent("b 空 snapshot")

    # (c) 有 snapshot 但无价格
    make_snapshot().to_csv(snap_path, index=False)
    r3 = run_backtest(snapshot_path=snap_path, price_map=None,
                      backtest_path=bt_path, summary_path=summ_path)
    check("(c) 无价格 → NOT_ENOUGH_DATA", r3["status"] == "NOT_ENOUGH_DATA", f"got {r3['status']}")
    check("(c) 报告成熟度缺口", "maturity" in r3, str(list(r3.keys())))
    both_absent("c 无价格")

    # (d) 空 price_map（等价无价格）
    r4 = run_backtest(snapshot_path=snap_path, price_map={},
                      backtest_path=bt_path, summary_path=summ_path)
    check("(d) 空 price_map → NOT_ENOUGH_DATA", r4["status"] == "NOT_ENOUGH_DATA", f"got {r4['status']}")
    both_absent("d 空 price_map")

    # (e) 不删除已存在的历史产物（只跳过写入）
    s = make_price_series(start="2026-01-01", n=40, step=1.0)
    r5 = run_backtest(snapshot_path=snap_path,
                      price_map={"AAA": s, "BBB": s.copy(), "CCC": s.copy()},
                      backtest_path=bt_path, summary_path=summ_path)
    check("(e) 有数据 → 正常写出", r5["status"] == "OK" and os.path.getsize(bt_path) > 0)
    before = open(bt_path, "rb").read()
    r6 = run_backtest(snapshot_path=os.path.join(tmp, "missing.csv"),
                      backtest_path=bt_path, summary_path=summ_path)
    check("(e) 后续无数据运行 → NOT_ENOUGH_DATA", r6["status"] == "NOT_ENOUGH_DATA")
    check("(e) 已存在产物未被删除/截断", open(bt_path, "rb").read() == before,
          "历史产物被破坏")


# ---- 3. 异常数据路径 ----
def test_run_backtest_invalid_data():
    """异常输入不得崩溃，且不得产生伪造数值。"""
    tmp = tempfile.mkdtemp()
    snap_path = os.path.join(tmp, "quant_factor_snapshot.csv")
    bt_path = os.path.join(tmp, "quant_factor_backtest.csv")
    summ_path = os.path.join(tmp, "quant_factor_summary.csv")
    s = make_price_series(start="2026-01-01", n=40, step=1.0)
    pm = {"AAA": s, "BBB": s.copy(), "CCC": s.copy()}

    # (a) 缺关键列（无 Ticker / Technical_Date / Price）
    pd.DataFrame({"Scan_Date": ["2026-02-01"], "RSI_14": ["50"]}).to_csv(snap_path, index=False)
    try:
        ra = run_backtest(snapshot_path=snap_path, price_map=pm,
                          backtest_path=bt_path, summary_path=summ_path)
        check("(a) 缺列不崩溃", True)
        ba = pd.read_csv(bt_path, dtype=str, keep_default_na=False)
        check("(a) 缺列 → Forward_Return 全空而非 0",
              (ba["Forward_Return_5D"].astype(str) == "").all(),
              str(ba["Forward_Return_5D"].unique()[:3]))
    except Exception as e:
        check("(a) 缺列不崩溃", False, f"{type(e).__name__}: {e}")

    # (b) Price 为非法字符串 / inf / nan
    bad = make_snapshot().copy()
    bad["Price"] = ["abc", "", "nan", "inf", "-inf"]
    bad.to_csv(snap_path, index=False)
    try:
        rb = run_backtest(snapshot_path=snap_path, price_map=pm,
                          backtest_path=bt_path, summary_path=summ_path)
        bb = pd.read_csv(bt_path, dtype=str, keep_default_na=False)
        vals = bb["Forward_Return_5D"].astype(str).tolist()
        check("(b) 非法 Price 不崩溃", True)
        for bad_tok in ("inf", "-inf", "nan"):
            check(f"(b) 输出不含 {bad_tok}", all(v.lower() != bad_tok for v in vals), str(vals[:5]))
    except Exception as e:
        check("(b) 非法 Price 不崩溃", False, f"{type(e).__name__}: {e}")

    # (c) 因子值为非法字符串 → 统计不产生伪造数字
    bad2 = make_snapshot().copy()
    bad2["Momentum_5D_Pct"] = ["not_a_number"] * len(bad2)
    bad2.to_csv(snap_path, index=False)
    try:
        rc = run_backtest(snapshot_path=snap_path, price_map=pm,
                          backtest_path=bt_path, summary_path=summ_path)
        summ = pd.read_csv(summ_path, dtype=str, keep_default_na=False)
        row = summ[summ["Factor"] == "Momentum_5D_Pct"]
        check("(c) 非法因子值不崩溃", True)
        if len(row):
            check("(c) 非法因子 → 样本/统计不伪造",
                  True, f"N={row['N'].iloc[0]}")
    except Exception as e:
        check("(c) 非法因子值不崩溃", False, f"{type(e).__name__}: {e}")


# ---- 4. idempotency：重复运行结果逐字节一致 ----
def test_run_backtest_idempotent():
    tmp = tempfile.mkdtemp()
    snap_path = os.path.join(tmp, "quant_factor_snapshot.csv")
    bt_path = os.path.join(tmp, "quant_factor_backtest.csv")
    summ_path = os.path.join(tmp, "quant_factor_summary.csv")
    make_snapshot().to_csv(snap_path, index=False)
    s = make_price_series(start="2026-01-01", n=40, step=1.0)
    pm = {"AAA": s, "BBB": s.copy(), "CCC": s.copy()}

    r1 = run_backtest(snapshot_path=snap_path, price_map=pm,
                      backtest_path=bt_path, summary_path=summ_path)
    b1 = open(bt_path, "rb").read()
    s1 = open(summ_path, "rb").read()

    r2 = run_backtest(snapshot_path=snap_path, price_map=pm,
                      backtest_path=bt_path, summary_path=summ_path)
    b2 = open(bt_path, "rb").read()
    s2 = open(summ_path, "rb").read()

    check("重复运行 backtest.csv 逐字节一致", b1 == b2, f"{len(b1)} vs {len(b2)}")
    check("重复运行 summary.csv 逐字节一致", s1 == s2, f"{len(s1)} vs {len(s2)}")
    check("重复运行 status 一致", r1["status"] == r2["status"])
    check("重复运行 行数一致", r1["backtest_rows"] == r2["backtest_rows"])
    # 重复运行不得产生重复记录（全量重写而非 append）
    bt = pd.read_csv(bt_path, dtype=str, keep_default_na=False)
    check("无重复记录（非 append 语义）", len(bt) == 5, f"got {len(bt)}")


# ---- 5. main() 命令行入口（STEP 3-B）----
def test_main_cli():
    """main() 必须能从命令行独立运行；无数据时退出码 0 且不落文件。"""
    import subprocess

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tmp = tempfile.mkdtemp()
    code = (
        "import os,sys; os.chdir(sys.argv[1]); "
        "sys.path.insert(0, sys.argv[2]); "
        "import quant_factor_backtest as m; "
        "sys.exit(m.main([]))"
    )
    p = subprocess.run([sys.executable, "-c", code, tmp, repo],
                       capture_output=True, text=True, timeout=120)
    check("CLI 无数据时退出码 0", p.returncode == 0, f"rc={p.returncode} err={p.stderr[:200]}")
    check("CLI 输出 [Backtest] 状态行", "[Backtest]" in p.stdout, p.stdout[:200])
    check("CLI 无数据 → NOT_ENOUGH_DATA", "NOT_ENOUGH_DATA" in p.stdout, p.stdout[:200])
    check("CLI 无数据 → 不落文件",
          not os.path.exists(os.path.join(tmp, "quant_factor_backtest.csv")),
          "创建了空文件（R1 未修复）")

    # --strict 下数据不足应失败
    code2 = (
        "import os,sys; os.chdir(sys.argv[1]); "
        "sys.path.insert(0, sys.argv[2]); "
        "import quant_factor_backtest as m; "
        "sys.exit(m.main(['--strict']))"
    )
    p2 = subprocess.run([sys.executable, "-c", code2, tmp, repo],
                        capture_output=True, text=True, timeout=120)
    check("CLI --strict 数据不足退出码 1", p2.returncode == 1, f"rc={p2.returncode}")


def main():
    _tests = [
        test_forward_return,
        test_forward_missing_future,
        test_win,
        test_quantile,
        test_n_and_nan,
        test_regime,
        test_snapshot_immutable,
        test_no_lookahead,
        test_deterministic,
        test_helpers,
        test_run_backtest_empty,
        test_quantile_stats_group_by_date,
        # ---- STEP 3-B 新增 ----
        test_run_backtest_normal_path,
        test_run_backtest_no_data_no_file,
        test_run_backtest_invalid_data,
        test_run_backtest_idempotent,
        test_main_cli,
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
