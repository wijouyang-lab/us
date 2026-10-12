# -*- coding: utf-8 -*-
"""盈亏机械性测试锁死（PnL is mechanical-only）。

核心原则：组合的盈亏（市值 / 浮盈 / 总权益 / 总盈亏 / 收益率 / 仓位占比）是
**纯机械计算**，由价格与持仓直接推导，**与任何 AI / LLM / 网络调用无关**。

本测试不 import、不执行任何 AI 模块，分三层把这条原则锁死：

  Test 1（静态，AST 扫描函数体）：
      断言 mark_to_market / build_portfolio / app.js positionCard 的函数体里
      **不含**任何 AI / LLM / 网络调用关键词（_model_stream_text、ClawSocketClient、
      anthropic、openai、requests.、urllib、httpx、urlopen、gpt、claude、completion、
      .chat(、fetch(）。
      这样一旦未来有人把 AI 调用写进盈亏计算路径，静态扫描会立刻失败。

  Test 2（运行时，驱动真实 build_portfolio）：
      用临时数据目录 + mock CSV 驱动真实代码，断言 6 条不变量精确成立：
        total_equity == cash + stock_value
        total_pnl    == total_equity - initial_capital
        return_pct   == total_pnl / initial_capital * 100
        unrealized_pnl == Σ positions.unrealized_pnl
        stock_value    == Σ positions.market_value
        open_pct       == stock_value / total_equity * 100

  Test 3（隔离，AI 字段不污染盈亏）：
      断言盈亏路径的输出里**不出现** ai_score / final_score / quant_score 等 AI 字段；
      且即使持仓 CSV 里多带一列 AI_Score（含空值），盈亏计算不受影响、结果不变。
"""
import ast
import json
import os
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# 盈亏计算路径里绝对不允许出现的 AI / 网络调用关键词（小写匹配）
AI_NET_TOKENS = (
    "_model_stream_text",
    "clawsocketclient",
    "clawsocket",
    "anthropic",
    "openai",
    "requests.",
    "urllib",
    "httpx",
    "urlopen",
    "gpt",
    "claude",
    "completion",
    ".chat(",
    "fetch(",
)

# AI / 评分相关字段名（用于隔离测试，小写匹配）
AI_SCORE_KEYS = {"ai_score", "final_score", "quant_score", "ai", "final", "quant"}


# --------------------------------------------------------------------------- #
# 静态扫描辅助
# --------------------------------------------------------------------------- #
def _py_function_source(py_path: Path, func_name: str) -> str:
    src = py_path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            seg = ast.get_source_segment(src, node)
            assert seg is not None, f"无法提取 {func_name} 源码段"
            return seg
    raise AssertionError(f"{func_name} 未找到于 {py_path}")


def _js_function_source(js_path: Path, func_name: str) -> str:
    js = js_path.read_text(encoding="utf-8")
    idx = js.find(f"function {func_name}(")
    if idx < 0:
        idx = js.find(f"{func_name} = function")
    assert idx >= 0, f"{func_name} 未找到于 {js_path}"
    brace_start = js.find("{", idx)
    depth = 0
    i = brace_start
    while i < len(js):
        c = js[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return js[idx:i + 1]
        i += 1
    raise AssertionError(f"{func_name} 括号不匹配")


def _assert_no_ai_tokens(body: str, label: str):
    lowered = body.lower()
    for tok in AI_NET_TOKENS:
        assert tok not in lowered, (
            f"盈亏锁死被违反 @ {label}：函数体内发现禁止的 AI/网络关键词 {tok!r}\n"
            f"——盈亏计算路径不得包含任何 AI / LLM / 网络调用。"
        )


# --------------------------------------------------------------------------- #
# Test 1：静态锁死 —— 盈亏函数体不含 AI / 网络调用
# --------------------------------------------------------------------------- #
def test_mark_to_market_has_no_ai_network_calls():
    body = _py_function_source(_REPO_ROOT / "portfolio_50000.py", "mark_to_market")
    _assert_no_ai_tokens(body, "portfolio_50000.mark_to_market")
    # 正向确认：它是机械计算（Decimal 算术 + 写入 Market_Value / Unrealized_PnL）
    assert "Decimal" in body
    assert "Market_Value" in body and "Unrealized_PnL" in body


def test_build_portfolio_summary_has_no_ai_network_calls():
    body = _py_function_source(_REPO_ROOT / "dashboard_export.py", "build_portfolio")
    _assert_no_ai_tokens(body, "dashboard_export.build_portfolio")
    # 正向确认：汇总字段从 positions 派生（单一数据源 + 不变量）
    assert "_stock_value" in body
    assert "_total_equity" in body
    assert "sum(" in body


def test_positioncard_has_no_ai_network_calls():
    body = _js_function_source(_REPO_ROOT / "app.js", "positionCard")
    _assert_no_ai_tokens(body, "app.js positionCard")
    # 正向确认：positionCard 只读取并展示盈亏字段，不重算
    assert "unrealized_pnl" in body
    assert "market_value" in body


# --------------------------------------------------------------------------- #
# Test 2：运行时锁死 —— 真实 build_portfolio 的不变量
# --------------------------------------------------------------------------- #
def _write_mock_portfolio(data_dir: Path, with_ai_score: bool):
    """写入 4 个数据文件。3 只 OPEN 持仓，市值之和=37000，浮盈之和=3000。

    with_ai_score=True 时，positions.csv 多带一列 AI_Score（含空值），
    用于隔离测试（该列必须被盈亏路径忽略）。
    """
    meta = {
        "portfolio_id": "P50K",
        "initial_capital": 50000.0,
        "start_date": "2026-01-02",
        "unit_dollars": 5000.0,
        "max_open_positions": 10,
    }
    (data_dir / "portfolio_50000_meta.json").write_text(
        json.dumps(meta), encoding="utf-8")

    ai_col = ",AI_Score" if with_ai_score else ""
    rows = (
        "P50K,U1,AAPL,100,150.00,2026-01-05,15000.00,160.00,,100,16000.00,1000.00,6.67,31.25,,OPEN,0.85\n"
        "P50K,U2,MSFT,50,300.00,2026-02-10,15000.00,320.00,,100,16000.00,1000.00,6.67,31.25,,OPEN,0.92\n"
        "P50K,U3,TSLA,20,200.00,2026-03-01,4000.00,250.00,,100,5000.00,1000.00,25.00,9.77,,OPEN,\n"
    ) if with_ai_score else (
        "P50K,U1,AAPL,100,150.00,2026-01-05,15000.00,160.00,,100,16000.00,1000.00,6.67,31.25,,OPEN\n"
        "P50K,U2,MSFT,50,300.00,2026-02-10,15000.00,320.00,,100,16000.00,1000.00,6.67,31.25,,OPEN\n"
        "P50K,U3,TSLA,20,200.00,2026-03-01,4000.00,250.00,,100,5000.00,1000.00,25.00,9.77,,OPEN\n"
    )
    header = (
        "Portfolio_ID,Unit_ID,Ticker,Shares,Entry_Price,Entry_Date,Cost_Basis,"
        "Current_Price,Extended_Price,Extended_Time,Market_Value,Unrealized_PnL,"
        f"Unrealized_PnL_Pct,Weight_Pct,Stop_Loss,Status{ai_col}"
    )
    positions_csv = header + "\n" + rows
    (data_dir / "portfolio_50000_positions.csv").write_text(
        positions_csv, encoding="utf-8")

    (data_dir / "portfolio_50000_transactions.csv").write_text(
        "Date,Ticker,Action,Shares,Price,Amount,Realized_PnL,Reason,Unit_ID\n"
        "2026-03-01,TSLA,BUY,20,200.0,4000.0,0.0,init,U3\n",
        encoding="utf-8")

    history_csv = (
        "Date,Total_Equity,Cash,Stock_Value,Realized_PnL,Unrealized_PnL,Total_PnL,Return_Pct,Open_Positions\n"
        "2026-10-12,90700.0,53700.0,37000.0,4000.0,3000.0,40700.0,81.40,3\n"
    )
    (data_dir / "portfolio_50000_history.csv").write_text(
        history_csv, encoding="utf-8")


def _assert_invariants(pf):
    positions = pf["positions"]
    sum_mv = round(sum(p["market_value"] for p in positions), 2)
    sum_up = round(sum(p["unrealized_pnl"] for p in positions), 2)

    # 1) stock_value == Σ market_value
    assert pf["stock_value"] == pytest.approx(sum_mv, abs=0.01)
    # 2) total_equity == cash + stock_value（不变量）
    assert pf["total_equity"] == pytest.approx(
        round(pf["cash"] + pf["stock_value"], 2), abs=0.01)
    # 3) total_pnl == total_equity - initial_capital
    assert pf["total_pnl"] == pytest.approx(
        round(pf["total_equity"] - pf["initial_capital"], 2), abs=0.01)
    # 4) return_pct == total_pnl / initial_capital * 100
    assert pf["return_pct"] == pytest.approx(
        round(pf["total_pnl"] / pf["initial_capital"] * 100, 2), abs=0.01)
    # 5) unrealized_pnl == Σ positions.unrealized_pnl
    assert pf["unrealized_pnl"] == pytest.approx(sum_up, abs=0.01)
    # 6) open_pct == stock_value / total_equity * 100
    assert pf["open_pct"] == pytest.approx(
        round(pf["stock_value"] / pf["total_equity"] * 100, 2), abs=0.01)


def test_pnl_invariants_hold_at_runtime(tmp_path):
    from dashboard_export import build_portfolio  # noqa: E402

    _write_mock_portfolio(tmp_path, with_ai_score=True)
    pf = build_portfolio(tmp_path)
    assert pf is not None
    assert len(pf["positions"]) == 3

    # 期望的纯机械结果
    assert pf["stock_value"] == pytest.approx(37000.0, abs=0.01)
    assert pf["unrealized_pnl"] == pytest.approx(3000.0, abs=0.01)
    assert pf["cash"] == pytest.approx(53700.0, abs=0.01)
    assert pf["total_equity"] == pytest.approx(90700.0, abs=0.01)  # 53700 + 37000
    assert pf["total_pnl"] == pytest.approx(40700.0, abs=0.01)      # 90700 - 50000
    assert pf["return_pct"] == pytest.approx(81.40, abs=0.01)       # 40700/50000*100
    assert pf["open_pct"] == pytest.approx(40.79, abs=0.01)         # 37000/90700*100

    _assert_invariants(pf)


# --------------------------------------------------------------------------- #
# Test 3：隔离锁死 —— AI 字段不污染盈亏路径
# --------------------------------------------------------------------------- #
def test_ai_score_fields_absent_from_pnl_path(tmp_path):
    from dashboard_export import build_portfolio  # noqa: E402

    _write_mock_portfolio(tmp_path, with_ai_score=True)
    pf = build_portfolio(tmp_path)
    assert pf is not None

    # 顶层 portfolio 不得含 AI / 评分键
    top_keys_lower = {k.lower() for k in pf.keys()}
    assert not (AI_SCORE_KEYS & top_keys_lower), (
        f"盈亏顶层出现 AI 字段：{AI_SCORE_KEYS & top_keys_lower}")

    # 每只持仓不得含 AI / 评分键（AI_Score 列必须被忽略）
    for p in pf["positions"]:
        pkeys_lower = {k.lower() for k in p.keys()}
        assert not (AI_SCORE_KEYS & pkeys_lower), (
            f"持仓出现 AI 字段：{AI_SCORE_KEYS & pkeys_lower} -> {p.get('ticker')}")


def test_pnl_robust_when_ai_score_missing_or_none(tmp_path):
    """即使 AI_Score 列缺失 / 为空，盈亏计算不受影响、结果与有该列时完全一致。"""
    from dashboard_export import build_portfolio  # noqa: E402

    # 有 AI_Score 列（含空值）
    d_with = tmp_path / "with_ai"
    d_with.mkdir()
    _write_mock_portfolio(d_with, with_ai_score=True)
    pf_with = build_portfolio(d_with)

    # 无 AI_Score 列
    d_without = tmp_path / "without_ai"
    d_without.mkdir()
    _write_mock_portfolio(d_without, with_ai_score=False)
    pf_without = build_portfolio(d_without)

    # 两者盈亏完全一致 —— 证明 AI 字段与盈亏计算彻底隔离
    for key in ("stock_value", "unrealized_pnl", "total_equity",
                "total_pnl", "return_pct", "open_pct", "cash"):
        assert pf_with[key] == pytest.approx(pf_without[key], abs=0.01), (
            f"AI_Score 列的存在改变了 {key}：{pf_with[key]} vs {pf_without[key]}")
