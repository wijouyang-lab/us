#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""serenity 联网工具的 executor 层。

三个工具（web_search / ticker_news / company_facts）：
- `web_search` / `ticker_news` 复用 `news_fetch_util`（零导入期副作用）
- `company_facts` 直接用 yfinance（**不导入 scan.py** —— scan 有周末 `sys.exit(0)`、
  模块级网络预检 `_ai_preflight()`、以及会重写被跟踪文件 `scan_version.txt` 的
  `update_version_marker()`，导入即可能致命）

安全护栏
--------
1. **无 URL 参数**：三个 `input_schema` 都没有 `url` / `endpoint` 字段 →
   结构上消除 SSRF（端点由 `news_fetch_util` 内部固定为 Google News / Yahoo RSS）。
2. **超时**：`web_search` 10s、`ticker_news` 8s（经 `news_fetch_util` 的 `timeout` 参数）；
   `company_facts` 由 yfinance 自身超时 + 异常捕获兜底。
3. **返回大小上限**：条数 ≤ 8 / ≤ 6；标题 ≤ 200 字符；`facts` JSON ≤ 2000 字符。
4. **参数校验**：`ticker` 必须匹配 `^[A-Z.]{1,6}$`；`query` 非空且 ≤ 200 字符。

导入期约定
----------
本模块顶层**只 import `re` / `os` / `sys`**（标准库，无网络、无 env 读取、无输出）。
所有重依赖（`news_fetch_util` / `yfinance` / `json` / `datetime`）都在**函数内**延迟导入，
因此 `import serenity_tools` 是零副作用的（可被 CI 安全检查断言）。
"""
from __future__ import annotations

import os
import re
import sys

# `skills/` 不在 sys.path 上时，`import news_fetch_util` 会失败 ——
# 与 skills/run_serenity.py:44-47 的 _REPO_ROOT_IMPORT 做法一致（无输出、无网络副作用）。
_REPO_ROOT_IMPORT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT_IMPORT not in sys.path:
    sys.path.insert(0, _REPO_ROOT_IMPORT)

# 股票代码校验（大写 + 点，用于 BRK.B 这类）；故意不做小写归一化：
# 小写输入一律判为非法，避免模型把普通词当代码传进来。
_TICKER_RE = re.compile(r"^[A-Z.]{1,6}$")

_MAX_RESULTS = 8          # web_search 条数上限
_MAX_TICKER_ITEMS = 6     # ticker_news 条数上限
_MAX_TITLE = 200          # 标题字符上限
_MAX_QUERY = 200          # 查询字符上限
_MAX_FACTS_JSON = 2000    # facts 序列化字符上限


# --------------------------------------------------------------------------- #
# 工具 1：web_search
# --------------------------------------------------------------------------- #
def tool_web_search(query: str, *, max_items: int = 8) -> dict:
    """搜索公开新闻标题/链接，用于核验公告、客户、认证、产能等是否存在。

    返回: {"results": [{"title","link","date_str","age_tag","source"}], "count": N, "error": null}
    失败: {"results": [], "count": 0, "error": "<type>: <msg>"}
    """
    if not isinstance(query, str) or not query.strip():
        return {"results": [], "count": 0, "error": "invalid_query"}
    query = query.strip()[:_MAX_QUERY]
    if not query:
        return {"results": [], "count": 0, "error": "empty_query"}

    try:
        from news_fetch_util import rss_search_google
    except ImportError as e:
        return {"results": [], "count": 0, "error": f"import_error: {e}"}

    try:
        try:
            limit = max(1, min(int(max_items), _MAX_RESULTS))
        except (TypeError, ValueError):
            limit = _MAX_RESULTS
        items = rss_search_google(query, max_items=limit, timeout=10.0)
        results = [{
            "title": (it.get("title") or "")[:_MAX_TITLE],
            "link": it.get("link") or "",
            "date_str": it.get("date_str") or "",
            "age_tag": it.get("age_tag") or "",
            "source": it.get("source") or "Google News",
        } for it in list(items)[:limit]]
        return {"results": results, "count": len(results), "error": None}
    except Exception as e:                                     # noqa: BLE001
        return {"results": [], "count": 0, "error": f"{type(e).__name__}: {e}"}


# --------------------------------------------------------------------------- #
# 工具 2：ticker_news
# --------------------------------------------------------------------------- #
def tool_ticker_news(ticker: str, *, max_items: int = 6) -> dict:
    """取某只股票最近的新闻标题（含来源/时间）。

    返回: {"ticker", "items": [{"title","link","source","date_str","age_tag"}], "count", "error": null}
    失败: {"ticker": ticker, "items": [], "error": "<...>"}
    """
    if not isinstance(ticker, str) or not _TICKER_RE.match(ticker):
        return {"ticker": str(ticker), "items": [], "count": 0, "error": "invalid_ticker"}

    try:
        from news_fetch_util import fetch_ticker_news
    except ImportError as e:
        return {"ticker": ticker, "items": [], "count": 0, "error": f"import_error: {e}"}

    try:
        try:
            limit = max(1, min(int(max_items), _MAX_TICKER_ITEMS))
        except (TypeError, ValueError):
            limit = _MAX_TICKER_ITEMS
        items = fetch_ticker_news(ticker, max_items=limit, timeout=8.0)
        results = [{
            "title": (it.get("title") or "")[:_MAX_TITLE],
            "link": it.get("link") or "",
            "source": it.get("source") or "",
            "date_str": it.get("date_str") or "",
            "age_tag": it.get("age_tag") or "",
        } for it in list(items)[:limit]]
        return {"ticker": ticker, "items": results, "count": len(results), "error": None}
    except Exception as e:                                     # noqa: BLE001
        return {"ticker": ticker, "items": [], "count": 0, "error": f"{type(e).__name__}: {e}"}


# --------------------------------------------------------------------------- #
# 工具 3：company_facts
# --------------------------------------------------------------------------- #
# 12 个对外字段名 → yfinance `info` 的**原始键**。
# ⚠️ 映射表照抄 scan.py:667-678 的 _fetch_fundamental_one()（它用 _safe_info_float(info, "trailingPE") 等）；
#    yfinance 的 info 里**没有** "PE_TTM" 这类友好名，若直接按友好名取键会永远取不到值。
_YF_KEY_MAP = (
    ("PE_TTM", ("trailingPE",)),
    ("PE_Forward", ("forwardPE",)),
    ("EPS_TTM", ("trailingEps", "epsTrailingTwelveMonths")),
    ("PB", ("priceToBook",)),
    ("EPS_Forward", ("epsForward",)),
    ("Earnings_Growth", ("earningsGrowth",)),
    ("Revenue_Growth", ("revenueGrowth",)),
    ("ROE", ("returnOnEquity",)),
    ("Profit_Margin", ("profitMargins",)),
    ("Operating_Cashflow", ("operatingCashflow",)),
    ("Free_Cashflow", ("freeCashflow",)),
    ("Market_Cap", ("marketCap",)),
)
_FACT_KEYS = tuple(name for name, _ in _YF_KEY_MAP)


def tool_company_facts(ticker: str) -> dict:
    """取公司公开财务事实（12 个固定字段，来自 yfinance）。

    返回: {"ticker", "facts": {...12 键...}, "asof": "<UTC 日期>", "source": "yfinance", "error": null}
    失败: {"ticker", "facts": {}, "source": "yfinance", "error": "<...>"}
    """
    if not isinstance(ticker, str) or not _TICKER_RE.match(ticker):
        return {"ticker": str(ticker), "facts": {}, "source": "yfinance", "error": "invalid_ticker"}

    try:
        import yfinance as yf
    except ImportError as e:
        return {"ticker": ticker, "facts": {}, "source": "yfinance", "error": f"import_error: {e}"}

    try:
        info = yf.Ticker(ticker).info or {}
        facts = {}
        for name, raw_keys in _YF_KEY_MAP:
            for raw in raw_keys:
                if raw in info and info[raw] is not None:
                    val = info[raw]
                    if isinstance(val, str):
                        val = val[:50]
                    facts[name] = val
                    break
        if not facts:
            return {"ticker": ticker, "facts": {}, "source": "yfinance",
                    "error": "no_facts_returned"}

        # 大小上限：序列化 ≤ 2000 字符；超出则按 _FACT_KEYS 顺序逐个回退（保留靠前字段）
        import json as _json
        if len(_json.dumps(facts, ensure_ascii=False, default=str)) > _MAX_FACTS_JSON:
            trimmed = {}
            for k in _FACT_KEYS:
                if k not in facts:
                    continue
                trimmed[k] = facts[k]
                if len(_json.dumps(trimmed, ensure_ascii=False, default=str)) > _MAX_FACTS_JSON:
                    trimmed.pop(k)
                    break
            facts = trimmed

        from datetime import datetime, timezone
        return {
            "ticker": ticker,
            "facts": facts,
            "asof": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "source": "yfinance",
            "error": None,
        }
    except Exception as e:                                     # noqa: BLE001
        return {"ticker": ticker, "facts": {}, "source": "yfinance",
                "error": f"{type(e).__name__}: {e}"}


# --------------------------------------------------------------------------- #
# 工具 schema（给模型看的）
# --------------------------------------------------------------------------- #
TOOLS = [
    {
        "name": "web_search",
        "description": "搜索公开新闻标题和链接（Google News RSS）。用于核验公告、客户、认证、"
                       "产能等是否存在。返回标题/链接/日期，不含正文。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词（≤ 200 字符）"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "ticker_news",
        "description": "取某只股票最近的新闻标题（含来源/时间）。用于交叉验证客户、订单、财报事件。",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "股票代码，如 SNPS"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "company_facts",
        "description": "取公司公开财务事实（PE / EPS / 收入增长 / 毛利 / 现金流 / 市值等 12 个字段），"
                       "数值来自 yfinance。**返回的数值由系统单独收录，你不需要、也不得把它们写进 "
                       "why 字段**，只用于判断哪些主张需要核验。",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "股票代码，如 SNPS"},
            },
            "required": ["ticker"],
        },
    },
]


# --------------------------------------------------------------------------- #
# 统一执行入口
# --------------------------------------------------------------------------- #
TOOL_REGISTRY = {
    "web_search": tool_web_search,
    "ticker_news": tool_ticker_news,
    "company_facts": tool_company_facts,
}


def execute_tool(name: str, args: dict) -> dict:
    """统一工具执行入口（供 agent loop 调用）。

    - name 未注册 → {"error": "unknown_tool", "name": name}
    - args 不是 dict → {"error": "invalid_args"}
    - 参数不匹配（缺/多/错类型）→ {"error": "bad_arguments: ..."}
    - executor 抛异常 → {"error": "<type>: <msg>"}
    任何情况下都**不抛出**，保证 loop 不会因为单个工具挂掉。
    """
    if name not in TOOL_REGISTRY:
        return {"error": "unknown_tool", "name": name}
    if not isinstance(args, dict):
        return {"error": "invalid_args"}
    try:
        return TOOL_REGISTRY[name](**args)
    except TypeError as e:      # 缺必填参数 / 多传参数 / 参数类型不符
        return {"error": f"bad_arguments: {e}"}
    except Exception as e:                                     # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}
