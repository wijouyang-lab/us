# -*- coding: utf-8 -*-
"""AI 原因回填（backfill_pending_reasons）单元测试。

背景：review.py 是脚本式模块（import 即跑整条流水线 + 多处 sys.exit 守卫），
无法直接 `import review` 做单元测试（会触发 AI 调用 / 网络 / 文件写入）。
本测试用 AST 从 review.py 源码提取 backfill_pending_reasons（及 flag 门控 if 块）
的真实源码，在隔离命名空间内 exec，避免触发流水线与网络。

测试对象即 review.py 的「当前真实源码」——改动后自动跟随，且能验证：
  1. 完整 JSON → 正确写回 Reason 并清 Pending_Reason（一次批量 AI 调用）
  2. 无 Pending 记录 → 不调 AI（mock 调用次数 = 0）
  3. AI 抛异常 → 函数不崩，Pending_Reason 保留
  4. flag 关闭时 backfill 不被调用（动态门控 + 静态 workflow 校验）
  5. JSON 格式错误 → 保留 Pending_Reason 不变（不写任何字段）
"""
import ast
import csv
import json
import os
import re
import tempfile
from datetime import datetime

import pytest

REVIEW_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "review.py")

TXN_COLS = [
    "Txn_ID", "Date", "Ticker", "Action", "Shares", "Price", "Amount",
    "Realized_PnL", "Cash_After", "Reason", "Recommendation_ID", "Scan_Date",
    "Portfolio_ID", "Unit_ID", "Pending_Reason",
]


def _load_backfill_function(fake_client_class, target_model="claude-opus-5-5"):
    """从 review.py 提取 backfill_pending_reasons 真实源码并 exec，返回函数。"""
    src = open(REVIEW_PATH, encoding="utf-8").read()
    tree = ast.parse(src)
    node = next(
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "backfill_pending_reasons"
    )
    func_src = ast.get_source_segment(src, node)
    ns = {
        "csv": csv, "json": json, "os": os, "re": re, "datetime": datetime,
        "ClawSocketClient": fake_client_class,
        "TARGET_MODEL": target_model,
        "print": lambda *a, **k: None,   # 静默打印
    }
    exec(func_src, ns)
    return ns["backfill_pending_reasons"]


def _find_gate_block_src():
    """提取 review.py 中 ENABLE_AI_REASON_BACKFILL 门控的 if 块真实源码。"""
    src = open(REVIEW_PATH, encoding="utf-8").read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            cond = ast.unparse(node.test)
            if "ENABLE_AI_REASON_BACKFILL" in cond:
                return ast.get_source_segment(src, node)
    return None


# ---------------- Fake ClawSocketClient 基础设施 ----------------
class _FakeCtx:
    def __init__(self, text):
        self._text = text

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    @property
    def text_stream(self):
        return [self._text]


class FakeMessages:
    def __init__(self, text):
        self.text = text
        self.call_count = 0

    def stream(self, **kw):
        self.call_count += 1
        return _FakeCtx(self.text)


class FakeClient:
    def __init__(self, text="", capture=None):
        self.messages = FakeMessages(text)
        if capture is not None:
            capture.append(self)


def _make_txn_csv(tmpdir, rows):
    path = os.path.join(tmpdir, "portfolio_50000_transactions.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TXN_COLS)
        w.writeheader()
        w.writerows(rows)
    return path


def _read_txn(tmpdir):
    with open(os.path.join(tmpdir, "portfolio_50000_transactions.csv"),
              encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _pending_sell(ticker, date, scan, pending="True", reason=""):
    return {
        "Txn_ID": "T_" + ticker, "Date": date, "Ticker": ticker, "Action": "SELL",
        "Shares": "10", "Price": "150", "Amount": "1500", "Realized_PnL": "-50",
        "Cash_After": "50000", "Reason": reason, "Recommendation_ID": "R_" + ticker,
        "Scan_Date": scan, "Portfolio_ID": "US-50000-001", "Unit_ID": "U1",
        "Pending_Reason": pending,
    }


def _buy_row(ticker):
    return {
        "Txn_ID": "B_" + ticker, "Date": "2026-10-07", "Ticker": ticker, "Action": "BUY",
        "Shares": "3", "Price": "120", "Amount": "360", "Realized_PnL": "",
        "Cash_After": "49640", "Reason": "", "Recommendation_ID": "RB_" + ticker,
        "Scan_Date": "2026-10-01", "Portfolio_ID": "US-50000-001", "Unit_ID": "U3",
        "Pending_Reason": "",
    }


# ============ 测试 1：完整 JSON → 写回 Reason + 清 Pending ============
def test_backfill_writes_reason_and_clears_pending():
    captured = []
    bf = _load_backfill_function(
        lambda *a, **k: FakeClient(
            '```json\n'
            '[{"ticker":"AAPL","reason":"跌破关键支撑位"},'
            '{"ticker":"MSFT","reason":"板块系统性风险"}]\n'
            '```',
            capture=captured,
        )
    )
    d = tempfile.mkdtemp()
    _make_txn_csv(d, [
        _pending_sell("AAPL", "2026-10-08", "2026-09-20"),
        _pending_sell("MSFT", "2026-10-08", "2026-09-25"),
        _buy_row("NVDA"),
    ])
    bf(d)
    out = {r["Ticker"]: r for r in _read_txn(d)}
    assert out["AAPL"]["Reason"] == "跌破关键支撑位"
    assert out["AAPL"]["Pending_Reason"] == ""
    assert out["MSFT"]["Reason"] == "板块系统性风险"
    assert out["MSFT"]["Pending_Reason"] == ""
    # 非 pending 的 BUY 记录完全不受影响
    assert out["NVDA"]["Pending_Reason"] == ""
    # 批量：AI 仅调用一次
    assert captured[0].messages.call_count == 1


# ============ 测试 2：无 Pending 记录 → 不调 AI ============
def test_no_pending_no_ai_call():
    captured = []
    bf = _load_backfill_function(lambda *a, **k: FakeClient("[]", capture=captured))
    d = tempfile.mkdtemp()
    _make_txn_csv(d, [_buy_row("NVDA")])
    bf(d)
    # 无 Pending → 提前 return，根本不会构造 client / 调 AI
    assert len(captured) == 0


# ============ 测试 3：AI 抛异常 → 函数不崩，保留 Pending ============
def test_ai_exception_does_not_crash():
    def raising_factory(*a, **k):
        raise RuntimeError("boom")

    bf = _load_backfill_function(raising_factory)
    d = tempfile.mkdtemp()
    _make_txn_csv(d, [_pending_sell("AAPL", "2026-10-08", "2026-09-20")])
    # 不应向外抛出异常
    bf(d)
    out = _read_txn(d)
    # 异常被内部兜底：Pending 保留，Reason 不变（下次再试）
    assert out[0]["Pending_Reason"] == "True"
    assert out[0]["Reason"] == ""


# ============ 测试 4a：flag 关闭时 backfill 不被调用（动态门控）============
def test_flag_off_backfill_not_called():
    gate = _find_gate_block_src()
    assert gate is not None, "未在 review.py 找到 ENABLE_AI_REASON_BACKFILL 门控块"
    calls = {"n": 0}

    def spy(data_dir="."):
        calls["n"] += 1

    for flag in (None, "0", "off", ""):
        if flag is None:
            os.environ.pop("ENABLE_AI_REASON_BACKFILL", None)
        else:
            os.environ["ENABLE_AI_REASON_BACKFILL"] = flag
        ns = {"backfill_pending_reasons": spy, "os": os,
              "print": lambda *a, **k: None}
        exec(gate, ns)
    # 任何非 "1" 的 flag（含未设置）都不应触发调用
    assert calls["n"] == 0


# ============ 测试 4b：flag 开启时 backfill 被调用 ============
def test_flag_on_backfill_called():
    gate = _find_gate_block_src()
    assert gate is not None
    calls = {"n": 0}

    def spy(data_dir="."):
        calls["n"] += 1

    os.environ["ENABLE_AI_REASON_BACKFILL"] = "1"
    try:
        ns = {"backfill_pending_reasons": spy, "os": os,
              "print": lambda *a, **k: None}
        exec(gate, ns)
    finally:
        os.environ.pop("ENABLE_AI_REASON_BACKFILL", None)
    assert calls["n"] == 1


# ============ 测试 4c：flag 未在任何 workflow 中设置（静态安全）============
def test_flag_not_set_in_any_workflow():
    repo = os.path.dirname(REVIEW_PATH)
    offenders = []
    for root, dirs, files in os.walk(repo):
        if ".git" in root:
            continue
        for fn in files:
            if fn.endswith((".yml", ".yaml")):
                p = os.path.join(root, fn)
                try:
                    txt = open(p, encoding="utf-8").read()
                except Exception:
                    continue
                if "ENABLE_AI_REASON_BACKFILL" in txt:
                    offenders.append(p)
    assert offenders == [], f"flag 出现在 workflow 中：{offenders}"


# ============ 测试 5：JSON 格式错误 → 保留 Pending 不变 ============
def test_malformed_json_preserves_pending():
    captured = []
    bf = _load_backfill_function(
        lambda *a, **k: FakeClient("这不是 JSON，也没有数组", capture=captured)
    )
    d = tempfile.mkdtemp()
    _make_txn_csv(d, [_pending_sell("AAPL", "2026-10-08", "2026-09-20")])
    bf(d)
    out = _read_txn(d)
    # 解析失败 → 不写任何字段，Pending_Reason 保留为原值
    assert out[0]["Pending_Reason"] == "True"
    assert out[0]["Reason"] == ""
    # AI 仍调用了一次（批量调用成功，仅解析失败），但写回被跳过
    assert len(captured) == 1
