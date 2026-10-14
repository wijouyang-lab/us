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

import portfolio_50000 as pf_mod  # 供 monkeypatch fetch_last_closes
from decimal import Decimal  # noqa: E402  （核验工具的测试夹具用）


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
    assert props <= {"query", "ticker", "label"}, \
        f"{tool['name']} 出现未登记的参数（需同步更新本断言）"


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


# --------------------------------------------------------------------------- #
# E2. 核验工具（段 3a-1）：verify_macro_series / verify_current_price
# --------------------------------------------------------------------------- #
_FRED_CSV_OK = "DATE,CPIAUCSL\n2025-07-01,320.10\n2025-08-01,321.00\n2026-07-01,332.00\n2026-08-01,334.98\n"


class _Resp:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _patch_fred(monkeypatch, text, capture=None):
    """把 news_fetch_util.new_session().get(...) 换成返回固定 CSV 的假 session。"""
    class _Sess:
        def get(self, url, timeout=None):
            if capture is not None:
                capture.append((url, timeout))
            return _Resp(text)
    monkeypatch.setattr(news_fetch_util, "new_session", lambda: _Sess())


def test_verify_macro_cpi_returns_shape(monkeypatch):
    cap = []
    _patch_fred(monkeypatch, _FRED_CSV_OK, cap)
    got = st.tool_verify_macro_series("CPI")
    assert got["error"] is None, got
    assert got["label"] == "CPI"
    assert got["value"] == 334.98
    assert got["prev"] == 332.00
    assert got["asof"] == "2026-08-01"
    assert "FRED:CPIAUCSL" in got["source"] and "independent" in got["source"]
    assert cap[0][0].endswith("id=CPIAUCSL") and cap[0][1] == 10.0


def test_verify_macro_rejects_unknown_label(monkeypatch):
    _patch_fred(monkeypatch, _FRED_CSV_OK)
    got = st.tool_verify_macro_series("GDP")
    assert got["value"] is None and got["error"] == "unknown_label"


def test_verify_macro_parses_yoy_from_fred(monkeypatch):
    _patch_fred(monkeypatch, _FRED_CSV_OK)
    got = st.tool_verify_macro_series("CPI")
    # 334.98 / 321.00 - 1 = 4.36%
    assert got["yoy"] == 4.36, got


def test_verify_macro_unemployment_has_no_yoy(monkeypatch):
    """失业率是百分比口径 → yoy 留空（与 CPI 的指数口径区分）。"""
    _patch_fred(monkeypatch, "DATE,UNRATE\n2026-09-01,4.20\n")
    got = st.tool_verify_macro_series("失业率")
    assert got["value"] == 4.20 and got["yoy"] is None, got


def test_verify_macro_yahoo_tnx_divided_by_10(monkeypatch):
    monkeypatch.setattr(pf_mod, "fetch_last_closes",
                        lambda ts: {"^TNX": {"current": Decimal("41.5"), "extended": None}})
    got = st.tool_verify_macro_series("10Y国债")
    assert got["error"] is None, got
    assert got["value"] == 4.15, got


def test_verify_macro_yahoo_tnx_already_percent(monkeypatch):
    """Yahoo 若已返回百分数（4.05）→ 不再 /10（防"0.405%"这种明显错误）。"""
    monkeypatch.setattr(pf_mod, "fetch_last_closes",
                        lambda ts: {"^TNX": {"current": Decimal("4.05"), "extended": None}})
    got = st.tool_verify_macro_series("10Y国债")
    assert got["value"] == 4.05, got


def test_verify_macro_network_failure_returns_error(monkeypatch):
    class _Boom:
        def get(self, url, timeout=None):
            raise TimeoutError("fred timeout")
    monkeypatch.setattr(news_fetch_util, "new_session", lambda: _Boom())
    got = st.tool_verify_macro_series("CPI")
    assert got["value"] is None and got["error"] == "TimeoutError: fred timeout"


def test_verify_macro_malformed_csv_returns_error(monkeypatch):
    """缺列 / 全为缺值 '.' → no_data（不编造）。"""
    _patch_fred(monkeypatch, "FOO,BAR\n2026-08-01,.\n")
    got = st.tool_verify_macro_series("核心CPI")
    assert got["value"] is None and got["error"] == "no_data"


def test_verify_price_returns_shape(monkeypatch):
    monkeypatch.setattr(pf_mod, "fetch_last_closes", lambda ts: {
        "CME": {"current": Decimal("278.03"), "extended": Decimal("277.90"),
                "extended_time": "10-13 18:09 ET"}})
    got = st.tool_verify_current_price("CME")
    assert got["error"] is None, got
    assert got["ticker"] == "CME" and got["price"] == 278.03
    assert got["extended"] == 277.90 and got["extended_time"] == "10-13 18:09 ET"
    assert got["source"] == "yfinance" and len(got["asof"]) == 10


def test_verify_price_rejects_invalid_ticker():
    got = st.tool_verify_current_price("../etc")
    assert got["price"] is None and got["error"] == "invalid_ticker"


def test_verify_price_accepts_hyphenated_ticker(monkeypatch):
    monkeypatch.setattr(pf_mod, "fetch_last_closes", lambda ts: {
        "BRK-B": {"current": Decimal("480.00"), "extended": None}})
    got = st.tool_verify_current_price("BRK-B")
    assert got["error"] is None and got["price"] == 480.00, got


def test_verify_price_falls_back_to_alt_symbol(monkeypatch):
    calls = []

    def _fake(ts):
        calls.append(list(ts))
        if ts[0] == "BRK-B":
            return {"BRK-B": {"current": Decimal("481.00"), "extended": None}}
        return {}

    monkeypatch.setattr(pf_mod, "fetch_last_closes", _fake)
    got = st.tool_verify_current_price("BRK.B")
    assert got["error"] is None and got["ticker"] == "BRK-B"
    assert got["price"] == 481.00
    assert calls == [["BRK.B"], ["BRK-B"]]


def test_verify_price_no_data_returns_error(monkeypatch):
    monkeypatch.setattr(pf_mod, "fetch_last_closes", lambda ts: {})
    got = st.tool_verify_current_price("CME")
    assert got["price"] is None and got["error"] == "no_data"


# --------------------------------------------------------------------------- #
# E3. 新工具的护栏
# --------------------------------------------------------------------------- #
_NEW_TOOL_NAMES = {"verify_macro_series", "verify_current_price"}


@pytest.mark.parametrize("tool", st.TOOLS, ids=[t["name"] for t in st.TOOLS])
def test_new_tools_schemas_have_no_url_field(tool):
    if tool["name"] not in _NEW_TOOL_NAMES:
        return
    props = set((tool.get("input_schema") or {}).get("properties") or {})
    assert not (props & {"url", "endpoint", "link", "host", "path"})
    assert props <= {"label", "ticker"}


def test_tools_registry_matches_tools_list():
    assert {t["name"] for t in st.TOOLS} == set(st.TOOL_REGISTRY)
    assert _NEW_TOOL_NAMES <= set(st.TOOL_REGISTRY)


def test_new_tools_are_callable_through_execute_tool(monkeypatch):
    _patch_fred(monkeypatch, _FRED_CSV_OK)
    got = st.execute_tool("verify_macro_series", {"label": "CPI"})
    assert got["value"] == 334.98
    assert st.execute_tool("verify_current_price", {"ticker": "aa1"})["error"] == "invalid_ticker"
