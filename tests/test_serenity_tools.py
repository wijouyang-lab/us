#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`skills/serenity_tools.py` 的工具 executor + 安全护栏单测（段 1B）。

全部 **不联网**：
· `news_fetch_util.rss_search_google` / `fetch_ticker_news` → monkeypatch；
· `yfinance.Ticker` → monkeypatch 成假类。

覆盖 5 组：
  A. execute_tool 分发与异常吞噬
  B. web_search（参数校验 / 截断 / 形状 / 失败路径）
  C. ticker_news（ticker 校验 / 形状 / 失败路径）
  D. company_facts（yfinance 键映射 / 空结果 / 大小截断 / 失败路径）
  E. 注册表一致性与安全护栏（含"导入期零副作用"子进程断言）
"""
import inspect
import json
import os
import subprocess
import sys
import time

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import news_fetch_util  # noqa: E402
from skills import serenity_tools as st  # noqa: E402


# --------------------------------------------------------------------------- #
# A. execute_tool 分发
# --------------------------------------------------------------------------- #
def test_execute_unknown_tool_returns_error():
    got = st.execute_tool("no_such_tool", {"x": 1})
    assert got["error"] == "unknown_tool"
    assert got["name"] == "no_such_tool"


@pytest.mark.parametrize("bad", [None, "string", 42, ["query"]])
def test_execute_invalid_args_type_returns_error(bad):
    got = st.execute_tool("web_search", bad)
    assert got == {"error": "invalid_args"}


def test_execute_bad_arguments_returns_error():
    got = st.execute_tool("web_search", {})           # 缺必填 query
    assert got["error"].startswith("bad_arguments")
    got2 = st.execute_tool("web_search", {"query": "x", "unexpected": 1})
    assert got2["error"].startswith("bad_arguments")


def test_execute_swallows_executor_exception(monkeypatch):
    def _boom(**_kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setitem(st.TOOL_REGISTRY, "web_search", _boom)
    got = st.execute_tool("web_search", {"query": "x"})
    assert got["error"] == "RuntimeError: kaboom"
    # 关键：不向上抛异常（loop 不会因单工具挂掉）


# --------------------------------------------------------------------------- #
# B. web_search
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad", ["", "   ", None, 123])
def test_web_search_empty_query_returns_error(bad):
    got = st.tool_web_search(bad)
    assert got["results"] == [] and got["count"] == 0
    assert got["error"] in ("invalid_query", "empty_query")


def test_web_search_long_query_truncated(monkeypatch):
    seen = {}

    def _fake(query, *, max_items=8, timeout=10.0):
        seen["query"] = query
        seen["timeout"] = timeout
        return []

    monkeypatch.setattr(news_fetch_util, "rss_search_google", _fake)
    st.tool_web_search("Q" * 500)
    assert len(seen["query"]) == 200          # 截断到 200
    assert seen["timeout"] == 10.0            # 超时硬编码 10s


def test_web_search_returns_expected_shape(monkeypatch):
    monkeypatch.setattr(news_fetch_util, "rss_search_google", lambda q, **kw: [{
        "title": "Fed signals shift - Reuters",
        "link": "https://example.com/a",
        "date_str": "10-13 09:12",
        "age_tag": "[🔥今日最新-权重最高]",
        "source": "Google News",
    }])
    got = st.tool_web_search("Fed")
    assert got["error"] is None and got["count"] == 1
    item = got["results"][0]
    assert set(item) == {"title", "link", "date_str", "age_tag", "source"}
    assert item["title"] == "Fed signals shift - Reuters"


def test_web_search_truncates_max_items(monkeypatch):
    ten = [{"title": f"H{i}", "link": "", "date_str": "", "age_tag": "", "source": ""}
           for i in range(10)]
    monkeypatch.setattr(news_fetch_util, "rss_search_google", lambda q, **kw: ten)
    got = st.tool_web_search("q", max_items=2)
    assert got["count"] == 2 and len(got["results"]) == 2


def test_web_search_error_path(monkeypatch):
    def _boom(q, **kw):
        raise TimeoutError("rss timeout")

    monkeypatch.setattr(news_fetch_util, "rss_search_google", _boom)
    got = st.tool_web_search("q")
    assert got["results"] == [] and got["count"] == 0
    assert got["error"] == "TimeoutError: rss timeout"


def test_web_search_result_title_truncated(monkeypatch):
    monkeypatch.setattr(news_fetch_util, "rss_search_google",
                        lambda q, **kw: [{"title": "T" * 500, "link": "", "date_str": "",
                                          "age_tag": "", "source": ""}])
    got = st.tool_web_search("q")
    assert len(got["results"][0]["title"]) == 200


# --------------------------------------------------------------------------- #
# C. ticker_news
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad", ["../etc", "aa1", "TOOLONGXX", "", "AA PL", None, 7])
def test_ticker_news_rejects_invalid_ticker(bad):
    got = st.tool_ticker_news(bad)
    assert got["items"] == [] and got["error"] == "invalid_ticker"


@pytest.mark.parametrize("good", ["BRK-B", "RDS-A", "BRK.B", "SNPS"])
def test_ticker_news_accepts_hyphenated_ticker(good, monkeypatch):
    """第四次运行暴露：池里的 BRK-B 被 `^[A-Z.]{1,6}$` 误拒 → 该 ticker 永远拿不到数据。"""
    monkeypatch.setattr(news_fetch_util, "fetch_ticker_news", lambda t, **kw: [])
    got = st.tool_ticker_news(good)
    assert got["error"] is None, f"{good} 应被接受"
    assert got["ticker"] == good


def test_ticker_news_returns_expected_shape(monkeypatch):
    monkeypatch.setattr(news_fetch_util, "fetch_ticker_news", lambda t, **kw: [{
        "title": "SNPS wins design win",
        "link": "https://y/1",
        "source": "Yahoo",
        "date_str": "10-13 08:40 ET",
        "age_tag": "[📄昨日-中等权重]",
    }])
    got = st.tool_ticker_news("SNPS")
    assert got["ticker"] == "SNPS" and got["count"] == 1 and got["error"] is None
    assert set(got["items"][0]) == {"title", "link", "source", "date_str", "age_tag"}


def test_ticker_news_error_path(monkeypatch):
    def _boom(t, **kw):
        raise RuntimeError("rss down")

    monkeypatch.setattr(news_fetch_util, "fetch_ticker_news", _boom)
    got = st.tool_ticker_news("SNPS")
    assert got["ticker"] == "SNPS" and got["items"] == []
    assert got["error"] == "RuntimeError: rss down"


# --------------------------------------------------------------------------- #
# D. company_facts
# --------------------------------------------------------------------------- #
class _FakeTicker:
    def __init__(self, ticker):
        self.ticker = ticker
        self.info = _FakeTicker.info_payload

    info_payload = {}


def _install_fake_yf(monkeypatch, payload=None, raises=None):
    import yfinance as yf

    if raises is not None:
        def _ctor(ticker):
            raise raises
        monkeypatch.setattr(yf, "Ticker", _ctor)
        return
    _FakeTicker.info_payload = payload or {}
    monkeypatch.setattr(yf, "Ticker", _FakeTicker)


def test_company_facts_returns_expected_shape(monkeypatch):
    # 用 yfinance 的**原始键**（trailingPE 等）—— 断言工具能映射到 12 个友好名
    _install_fake_yf(monkeypatch, {
        "trailingPE": 42.5, "forwardPE": 30.1, "trailingEps": 3.2, "priceToBook": 8.8,
        "epsForward": 4.4, "earningsGrowth": 0.15, "revenueGrowth": 0.22,
        "returnOnEquity": 0.31, "profitMargins": 0.24, "operatingCashflow": 123456,
        "freeCashflow": 98765, "marketCap": 1234567890,
    })
    got = st.tool_company_facts("SNPS")
    assert got["error"] is None and got["source"] == "yfinance"
    assert set(got["facts"]) == set(st._FACT_KEYS)          # 恰好 12 个
    assert got["facts"]["PE_TTM"] == 42.5                    # 原始键 → 友好名
    assert got["facts"]["Market_Cap"] == 1234567890
    assert len(got["asof"]) == 10                            # YYYY-MM-DD


@pytest.mark.parametrize("bad", ["../etc", "lower", "TOOLONGXX", None])
def test_company_facts_rejects_invalid_ticker(bad):
    got = st.tool_company_facts(bad)
    assert got["facts"] == {} and got["error"] == "invalid_ticker"


@pytest.mark.parametrize("good", ["BRK-B", "RDS-A"])
def test_company_facts_accepts_hyphenated_ticker(good, monkeypatch):
    _install_fake_yf(monkeypatch, {"trailingPE": 1.0})
    got = st.tool_company_facts(good)
    assert got["error"] is None, f"{good} 应被接受"
    assert got["facts"]["PE_TTM"] == 1.0


def test_company_facts_no_facts_returned_error(monkeypatch):
    _install_fake_yf(monkeypatch, {"someUnrelatedKey": 1})
    got = st.tool_company_facts("SNPS")
    assert got["facts"] == {} and got["error"] == "no_facts_returned"


# --------------------------------------------------------------------------- #
# D2. 符号回退（#5：池里写 BRK-B，模型可能传 BRK.B）
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("src,expected", [
    ("BRK.B", "BRK-B"), ("BRK-B", "BRK.B"), ("SNPS", None), ("A.B.C", "A-B-C"),
])
def test_alt_symbol(src, expected):
    assert st._alt_symbol(src) == expected


def test_company_facts_falls_back_to_alt_symbol(monkeypatch):
    """BRK.B 取不到 → 自动用 BRK-B 重试一次，并返回**实际生效的符号**。"""
    calls = []

    def _fake(t):
        calls.append(t)
        return {"PE_TTM": 1.0} if t == "BRK-B" else {}

    monkeypatch.setattr(st, "_yf_fetch", _fake)
    got = st.tool_company_facts("BRK.B")

    assert got["error"] is None
    assert got["ticker"] == "BRK-B"           # 返回实际符号（不是输入）
    assert got["facts"]["PE_TTM"] == 1.0
    assert calls == ["BRK.B", "BRK-B"]        # 恰好两次，顺序正确


def test_company_facts_falls_back_reverse_direction(monkeypatch):
    """反向也支持：输入 BRK-B 取不到 → 尝试 BRK.B。"""
    calls = []

    def _fake(t):
        calls.append(t)
        return {"PE_TTM": 2.0} if t == "BRK.B" else {}

    monkeypatch.setattr(st, "_yf_fetch", _fake)
    got = st.tool_company_facts("BRK-B")

    assert got["ticker"] == "BRK.B" and got["facts"]["PE_TTM"] == 2.0
    assert calls == ["BRK-B", "BRK.B"]


def test_company_facts_no_alt_call_without_separator(monkeypatch):
    """无 `.`/`-` 的普通 ticker 失败时**不得**多打一次网络。"""
    calls = []
    monkeypatch.setattr(st, "_yf_fetch", lambda t: (calls.append(t), {})[1])
    got = st.tool_company_facts("SNPS")
    assert got["error"] == "no_facts_returned"
    assert calls == ["SNPS"]


def test_company_facts_both_symbols_fail(monkeypatch):
    """两种写法都失败 → 仍返回 no_facts_returned，且 ticker 保持输入值。"""
    calls = []
    monkeypatch.setattr(st, "_yf_fetch", lambda t: (calls.append(t), {})[1])
    got = st.tool_company_facts("BRK.B")
    assert got["error"] == "no_facts_returned" and got["ticker"] == "BRK.B"
    assert calls == ["BRK.B", "BRK-B"]


def test_company_facts_truncates_large_facts(monkeypatch):
    # Market_Cap 放一个超大列表 → 序列化超 2000 字符 → 应被裁掉，保留靠前字段
    _install_fake_yf(monkeypatch, {"trailingPE": 1.0, "marketCap": list(range(600))})
    got = st.tool_company_facts("SNPS")
    assert got["error"] is None
    assert "PE_TTM" in got["facts"]
    assert "Market_Cap" not in got["facts"]
    assert len(json.dumps(got["facts"], ensure_ascii=False, default=str)) <= 2000


def test_company_facts_error_path(monkeypatch):
    _install_fake_yf(monkeypatch, raises=RuntimeError("yf exploded"))
    got = st.tool_company_facts("SNPS")
    assert got["facts"] == {} and got["source"] == "yfinance"
    assert got["error"] == "RuntimeError: yf exploded"


# --------------------------------------------------------------------------- #
# E. 注册表一致性与安全护栏
# --------------------------------------------------------------------------- #
def test_tools_list_matches_registry():
    assert {t["name"] for t in st.TOOLS} == set(st.TOOL_REGISTRY)


@pytest.mark.parametrize("tool", st.TOOLS, ids=[t["name"] for t in st.TOOLS])
def test_no_tool_schema_has_url_field(tool):
    props = set((tool.get("input_schema") or {}).get("properties") or {})
    assert not (props & {"url", "endpoint", "link", "host", "path"}), \
        f"{tool['name']} 不应接受任意 URL 类参数（SSRF 护栏）"
    # 且每个工具的参数都必须是显式白名单
    assert props <= {"query", "ticker"}


@pytest.mark.parametrize("fn_name", ["tool_web_search", "tool_ticker_news", "tool_company_facts"])
def test_tool_signatures_have_no_url_parameter(fn_name):
    params = set(inspect.signature(getattr(st, fn_name)).parameters)
    assert not (params & {"url", "endpoint"})


def test_tools_module_import_has_no_side_effects():
    """干净环境子进程 import：应无 stdout/stderr、且远快于任何网络调用。"""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("CLAWSOCKET_") and k not in ("PYTHONPATH",)}
    env["PYTHONPATH"] = _REPO_ROOT
    env["PYTHONUTF8"] = "1"
    t0 = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-c", "import serenity_tools; print('', end='')"],
        cwd=os.path.join(_REPO_ROOT, "skills"),
        env=env, capture_output=True, text=True, timeout=30,
    )
    elapsed = time.perf_counter() - t0
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == "" and proc.stderr == "", (proc.stdout, proc.stderr)
    assert elapsed < 5, f"导入耗时异常（可能有网络/IO 副作用）: {elapsed:.1f}s"
