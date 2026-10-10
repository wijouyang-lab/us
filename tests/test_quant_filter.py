# -*- coding: utf-8 -*-
"""quant_filter 纯函数单元测试。

只 import quant_filter（不 import scan，避免其模块级 sys.exit / 时间门控 / 环境变量校验）。
不触网、不写生产文件、不硬编码绝对日期、不调用真实 AI。
"""

import pandas as pd
import pytest

import quant_filter as qf


# ============================================================
# compute_20d_high：前 20 日高点
# ============================================================

def test_compute_20d_high_normal():
    # 25 根日线，取最近 20 根 High 的最大值
    highs = list(range(1, 26))  # 1..25，最近 20 根 = 6..25，max = 25
    df = pd.DataFrame({"High": highs})
    assert qf.compute_20d_high(df) == 25.0


def test_compute_20d_high_insufficient_data():
    # 不足 20 根：返回已有区间的最大值
    df = pd.DataFrame({"High": [10, 13, 11, 9, 12]})
    assert qf.compute_20d_high(df) == 13.0


def test_compute_20d_high_with_nan():
    # NaN 与 None 被丢弃后取有效值最大值
    df = pd.DataFrame({"High": [5.0, float("nan"), 8.0, None, 7.0]})
    assert qf.compute_20d_high(df) == 8.0


def test_compute_20d_high_all_nan():
    df = pd.DataFrame({"High": [float("nan"), float("nan")]})
    assert qf.compute_20d_high(df) is None


def test_compute_20d_high_empty_or_missing_column():
    assert qf.compute_20d_high(pd.DataFrame({"High": []})) is None
    assert qf.compute_20d_high(pd.DataFrame({"Close": [1, 2, 3]})) is None
    assert qf.compute_20d_high(None) is None


# ============================================================
# compute_rr_ratio：(target - price) / (price - stop_loss)
# ============================================================

def test_compute_rr_ratio_normal():
    assert qf.compute_rr_ratio(100, 95, 110) == pytest.approx(2.0)


def test_compute_rr_ratio_stop_at_or_above_price():
    # 止损 ≥ 现价：无下行风险，返回 None（fail-closed）
    assert qf.compute_rr_ratio(100, 100, 110) is None
    assert qf.compute_rr_ratio(100, 105, 110) is None


def test_compute_rr_ratio_target_below_price():
    # 目标 ≤ 现价：返回非正比值（严筛按 R/R ≥ 2.0 拒绝，而非 None）
    rr = qf.compute_rr_ratio(100, 95, 90)
    assert rr is not None
    assert rr < 0


def test_compute_rr_ratio_none_inputs():
    assert qf.compute_rr_ratio(None, 95, 110) is None
    assert qf.compute_rr_ratio(100, None, 110) is None
    assert qf.compute_rr_ratio(100, 95, None) is None


# ============================================================
# strict_filter：严筛（评分≥90 / R/R≥2.0 / 止损 2%-5% / ≤1板块 / ≤3只）
# ============================================================

def _row(ticker, score=95, price=100, stop=96, target=110, sector="Tech"):
    """构造一个默认可通过严筛的候选行。"""
    return {
        "Ticker": ticker,
        "Price": price,
        "Final_Score": score,
        "Stop_Loss": stop,
        "target_price": target,
        "Sector": sector,
    }


def test_strict_filter_all_pass():
    rows = [
        _row("AAA", sector="Tech"),
        _row("BBB", sector="Health"),
        _row("CCC", sector="Energy"),
    ]
    out = qf.strict_filter(rows)
    assert len(out) == 3
    assert [x["Ticker"] for x in out] == ["AAA", "BBB", "CCC"]


def test_strict_filter_score_below_min():
    rows = [
        _row("AAA", score=75),   # 评分 < 80（MIN_SCORE）→ 排除
        _row("BBB", score=95),
    ]
    out = qf.strict_filter(rows)
    assert [x["Ticker"] for x in out] == ["BBB"]


def test_strict_filter_score_between_old_and_new_threshold():
    # MIN_SCORE 由 90 下调到 80 后，评分落在 (80, 90) 的行应被新阈值放行
    # （旧阈值 90 会排除它）。本用例锁定该行为，防止阈值被误改回 90。
    row = {
        "Ticker": "MID",
        "Quant_Score": 82,   # 旧阈值 90 不过、新阈值 80 过
        "Price": 100,
        "Stop_Loss": 96,     # 止损距离 4% ∈ [2%, 5%]
        "target_price": 110,  # R/R = (110-100)/(100-96) = 2.5 ≥ 2.0
        "Sector": "MidCap",
    }
    out = qf.strict_filter([row])
    assert len(out) == 1
    assert out[0]["Ticker"] == "MID"
    assert out[0].get("_rr") is not None and out[0]["_rr"] >= 2.0


def test_strict_filter_rr_below_min():
    rows = [
        _row("AAA", target=104),  # R/R = (104-100)/4 = 1.0 < 2.0 → 排除
        _row("BBB", target=110),
    ]
    out = qf.strict_filter(rows)
    assert [x["Ticker"] for x in out] == ["BBB"]


def test_strict_filter_stop_distance_out_of_range():
    rows = [
        _row("AAA", stop=99),   # 止损距离 1% < 2% → 排除
        _row("BBB", stop=90),   # 止损距离 10% > 5% → 排除
        _row("CCC", stop=96),   # 4% → 通过
    ]
    out = qf.strict_filter(rows)
    assert [x["Ticker"] for x in out] == ["CCC"]


def test_strict_filter_sector_concentration():
    rows = [
        _row("AAA", sector="Tech"),
        _row("BBB", sector="Tech"),   # 同板块第二只 → 排除
        _row("CCC", sector="Health"),
    ]
    out = qf.strict_filter(rows)
    assert [x["Ticker"] for x in out] == ["AAA", "CCC"]


def test_strict_filter_caps_at_three():
    rows = [
        _row(f"T{i}", sector=f"S{i}") for i in range(5)
    ]
    out = qf.strict_filter(rows)
    assert len(out) == 3


def test_strict_filter_sorted_by_score_desc():
    rows = [
        _row("A", score=92, sector="S1"),
        _row("B", score=99, sector="S2"),
        _row("C", score=95, sector="S3"),
    ]
    out = qf.strict_filter(rows)
    assert [x["Ticker"] for x in out] == ["B", "C", "A"]


def test_strict_filter_missing_target_price_skipped():
    rows = [
        _row("AAA"),            # 有 target_price
        {"Ticker": "BBB", "Price": 100, "Final_Score": 95, "Stop_Loss": 96, "Sector": "Health"},  # 无 target → 跳过
    ]
    out = qf.strict_filter(rows)
    assert [x["Ticker"] for x in out] == ["AAA"]


def test_strict_filter_diagnostic_fields_attached():
    out = qf.strict_filter([_row("AAA")])
    assert len(out) == 1
    assert "_rr" in out[0]
    assert "_stop_dist" in out[0]
    assert out[0]["_rr"] == pytest.approx(2.5)
    assert out[0]["_stop_dist"] == pytest.approx(0.04)


# ============================================================
# load_positions：读持仓 CSV，防御容错
# ============================================================

def _write_csv(path, content):
    path.write_text(content, encoding="utf-8")


def test_load_positions_existing_file(tmp_path):
    p = tmp_path / "positions.csv"
    _write_csv(p, (
        "Ticker,Stop_Loss,Status\n"
        "adsk,120,OPEN\n"
        "ANET,90,ACTIVE\n"
        "isrg,75,CLOSED\n"
        "KR,50,\n"           # 空 Status → 视为 OPEN
        ",60,OPEN\n"          # 空 Ticker → 跳过
    ))
    tickers = qf.load_positions(str(p))
    assert tickers == ["ADSK", "ANET", "KR"]


def test_load_positions_missing_file(tmp_path):
    tickers = qf.load_positions(str(tmp_path / "nope.csv"))
    assert tickers == []


def test_load_positions_empty_file(tmp_path):
    p = tmp_path / "positions.csv"
    _write_csv(p, "Ticker,Stop_Loss,Status\n")  # 仅表头
    assert qf.load_positions(str(p)) == []


def test_load_positions_none_path():
    assert qf.load_positions(None) == []
    assert qf.load_positions("") == []


# ============================================================
# build_ai_input：收缩 AI 输入（持仓 + ≤3 候选）
# ============================================================

def _pool(tickers):
    """构造含 tickers 的池（每只带 Price/Final_Score/Sector）。"""
    return [
        {"Ticker": t, "Price": 100, "Final_Score": 95, "Sector": f"S{i}"}
        for i, t in enumerate(tickers)
    ]


def test_build_ai_input_positions_at_least_three():
    pool = _pool(["AAA", "BBB", "CCC", "DDD", "EEE"])
    positions = ["AAA", "BBB", "CCC", "DDD"]  # 4 持仓
    candidates = [
        {"Ticker": "EEE", "Price": 100, "_rr": 2.5},
        {"Ticker": "FFF", "Price": 100, "_rr": 2.4},
        {"Ticker": "GGG", "Price": 100, "_rr": 2.3},
    ]
    out = qf.build_ai_input(pool, positions, candidates)
    assert len(out) == 7  # 4 + 3
    # 持仓优先，标记 Core_Dragon + _is_position
    assert [x["Ticker"] for x in out[:4]] == ["AAA", "BBB", "CCC", "DDD"]
    assert all(x["Tag"] == "Core_Dragon" for x in out[:4])
    assert all(x.get("_is_position") for x in out[:4])
    # 候选标记 Candidate
    assert [x["Ticker"] for x in out[4:]] == ["EEE", "FFF", "GGG"]
    assert all(x["Tag"] == "Candidate" for x in out[4:])


def test_build_ai_input_positions_less_than_three():
    pool = _pool(["AAA", "BBB", "CCC", "DDD"])
    positions = ["AAA"]  # 1 持仓
    candidates = [
        {"Ticker": "BBB", "_rr": 2.5},
        {"Ticker": "CCC", "_rr": 2.4},
        {"Ticker": "DDD", "_rr": 2.3},
    ]
    out = qf.build_ai_input(pool, positions, candidates)
    assert len(out) == 4
    assert out[0]["Ticker"] == "AAA" and out[0]["_is_position"]
    assert [x["Ticker"] for x in out[1:]] == ["BBB", "CCC", "DDD"]


def test_build_ai_input_no_candidates():
    pool = _pool(["AAA", "BBB", "CCC"])
    positions = ["AAA", "BBB", "CCC"]
    out = qf.build_ai_input(pool, positions, [])
    assert len(out) == 3
    assert all(x["_is_position"] for x in out)


def test_build_ai_input_dedup_and_cap():
    # 候选与持仓重叠时持仓优先（候选被去重）；总数硬顶 7
    pool = _pool([f"T{i}" for i in range(10)])
    positions = ["T0", "T1", "T2", "T3"]
    candidates = [{"Ticker": "T1", "_rr": 2.5}] + [{"Ticker": f"C{i}", "_rr": 2.5} for i in range(8)]
    out = qf.build_ai_input(pool, positions, candidates)
    assert len(out) <= 7
    # T1 是持仓，候选中的 T1 被去重
    tickers = [x["Ticker"] for x in out]
    assert tickers.count("T1") == 1
    assert out[tickers.index("T1")]["_is_position"] is True


# generate_ai_report (scan.py:2590) 对以下字段做硬索引 x['字段']，缺失即 KeyError。
# 这些是 prompt 拼装契约的必填字段——任何一条缺失都会让整次 scan 崩在 2590 行。
PROMPT_REQUIRED_FIELDS = [
    "Name", "Price", "RSI", "乖离率(%)", "MACD趋势", "KDJ_J", "量比",
]


def test_build_ai_input_position_not_in_pool_has_all_prompt_fields():
    """回归核心：持仓不在 pool_data 中时（生产真实情形），行绝不能缺字段。

    这正是 2026-10-09 scan 首次真实运行崩溃的场景——
    pool_data 来自扫描候选池，不含持仓，旧代码退化为空 dict 行导致 x['Name'] KeyError。
    """
    pool = [{"Ticker": "ZZZ", "Name": "Other", "Price": 10, "RSI": 50,
             "乖离率(%)": 1.0, "MACD趋势": "up", "KDJ_J": 20, "量比": 1.0}]
    positions = ["AAPL", "MSFT", "NVDA", "TSLA"]  # 4 持仓，均不在 pool 中
    out = qf.build_ai_input(pool, positions, [])
    assert len(out) == 4
    for x in out:
        for k in PROMPT_REQUIRED_FIELDS:
            assert k in x, f"持仓 {x.get('Ticker')} 缺少 prompt 必填字段 {k}"
        assert x["Tag"] == "Core_Dragon"
        assert x["_is_position"] is True


def test_build_ai_input_position_in_pool_keeps_real_values():
    """持仓命中 pool_data 时，应复制真实字段值（不被默认值覆盖）。"""
    pool = [
        {"Ticker": "AAPL", "Name": "Apple", "Price": 229.5, "RSI": 42.1,
         "乖离率(%)": -2.3, "MACD趋势": "down", "KDJ_J": 15.0, "量比": 0.8},
        {"Ticker": "MSFT", "Name": "Microsoft", "Price": 410.0, "RSI": 55.0,
         "乖离率(%)": 1.1, "MACD趋势": "up", "KDJ_J": 60.0, "量比": 1.2},
    ]
    positions = ["AAPL", "MSFT"]
    out = qf.build_ai_input(pool, positions, [])
    by_t = {x["Ticker"]: x for x in out}
    assert by_t["AAPL"]["Name"] == "Apple"
    assert by_t["AAPL"]["Price"] == 229.5
    assert by_t["AAPL"]["RSI"] == 42.1
    assert by_t["AAPL"]["量比"] == 0.8


def test_build_ai_input_candidate_row_has_all_prompt_fields():
    """候选行同样兜底补全 prompt 必填字段。"""
    pool = []
    candidates = [
        {"Ticker": "BBB", "Price": 100, "_rr": 2.5},  # 缺 Name/RSI 等
        {"Ticker": "CCC", "Price": 100, "_rr": 2.4},
    ]
    out = qf.build_ai_input(pool, [], candidates)
    assert len(out) == 2
    for x in out:
        assert x["Tag"] == "Candidate"
        for k in PROMPT_REQUIRED_FIELDS:
            assert k in x, f"候选 {x.get('Ticker')} 缺少 prompt 必填字段 {k}"


def test_build_ai_input_positions_never_truncated_by_candidates():
    """#3 防御性回归（WEEKEND_IMPLEMENTATION_PLAN §3）：即使候选很多，持仓也恒优先保留，
    不被 AI_INPUT_MAX 截断；候选被限到 ≤3（§0.9 候选上限 = min(3, 7-持仓数)）。

    验证 4 持仓 + 10 候选 → 输出仍为 4 持仓全部保留 + ≤3 候选，总数 ≤7。
    对当前 out[:AI_INPUT_MAX] 与 #4 Diff D（持仓优先 + 候选动态上限）两种实现都成立。
    """
    pool = _pool([f"P{i}" for i in range(4)] + [f"C{i}" for i in range(10)])
    positions = ["P0", "P1", "P2", "P3"]
    candidates = [{"Ticker": f"C{i}", "Price": 100, "_rr": 2.5} for i in range(10)]
    out = qf.build_ai_input(pool, positions, candidates)
    pos_out = [x for x in out if x.get("_is_position")]
    assert len(pos_out) == 4, f"持仓应全部保留，实际 {len(pos_out)}"
    assert {x["Ticker"] for x in pos_out} == {"P0", "P1", "P2", "P3"}
    cand_out = [x for x in out if not x.get("_is_position")]
    assert len(cand_out) <= 3, f"候选应 ≤3，实际 {len(cand_out)}"
    assert len(out) <= 7, f"总数应 ≤7，实际 {len(out)}"


def test_build_ai_input_candidate_cap_exact():
    """#4 Diff D（§0.9）：候选上限 = min(3, AI_INPUT_MAX - 持仓数)，且持仓永不被截断。

    验证：
    - 4 持仓 + 10 候选 → 候选恰好 3、总数恰好 7（持仓 4 全保留）
    - 2 持仓 + 10 候选 → 候选仍 3（下限 3）、总数恰好 5
    - 0 持仓 + 10 候选 → 候选恰好 3（仍受 §0.9 候选上限约束，不铺满 7）
    """
    # 4 持仓 + 10 候选 → 候选恰好 3
    pool4 = _pool([f"P{i}" for i in range(4)] + [f"C{i}" for i in range(10)])
    out4 = qf.build_ai_input(pool4, ["P0", "P1", "P2", "P3"],
                             [{"Ticker": f"C{i}", "Price": 100, "_rr": 2} for i in range(10)])
    cand4 = [x for x in out4 if not x.get("_is_position")]
    pos4 = [x for x in out4 if x.get("_is_position")]
    assert len(pos4) == 4, f"4 持仓应全保留，实际 {len(pos4)}"
    assert len(cand4) == 3, f"候选应恰好 3，实际 {len(cand4)}"
    assert len(out4) == 7, f"总数应恰好 7，实际 {len(out4)}"

    # 2 持仓 + 10 候选 → 候选仍 3、总数 5
    pool2 = _pool([f"P{i}" for i in range(2)] + [f"C{i}" for i in range(10)])
    out2 = qf.build_ai_input(pool2, ["P0", "P1"],
                             [{"Ticker": f"C{i}", "Price": 100, "_rr": 2} for i in range(10)])
    cand2 = [x for x in out2 if not x.get("_is_position")]
    pos2 = [x for x in out2 if x.get("_is_position")]
    assert len(pos2) == 2, f"2 持仓应全保留，实际 {len(pos2)}"
    assert len(cand2) == 3, f"候选应恰好 3（下限），实际 {len(cand2)}"
    assert len(out2) == 5, f"总数应恰好 5，实际 {len(out2)}"

    # 0 持仓 + 10 候选 → 候选恰好 3（不铺满 7）
    pool0 = _pool([f"C{i}" for i in range(10)])
    out0 = qf.build_ai_input(pool0, [],
                             [{"Ticker": f"C{i}", "Price": 100, "_rr": 2} for i in range(10)])
    cand0 = [x for x in out0 if not x.get("_is_position")]
    assert len(cand0) == 3, f"无持仓时候选仍应 ≤3，实际 {len(cand0)}"
