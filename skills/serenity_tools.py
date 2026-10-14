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

# 股票代码校验（大写 + 点 + 连字符：BRK.B / BRK-B / RDS-A 这类都合法）；
# 故意不做小写归一化：小写输入一律判为非法，避免模型把普通词当代码传进来。
_TICKER_RE = re.compile(r"^[A-Z.\-]{1,6}$")

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


def _yf_fetch(ticker: str) -> dict:
    """单次 yfinance 调用 → 12 个友好名字段（取不到就返回空 dict）。"""
    import yfinance as yf
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
    return facts


def _alt_symbol(ticker: str) -> str | None:
    """给出替代 ticker 写法（Yahoo 惯例是连字符 `BRK-B`，模型可能传点号 `BRK.B`）。

    无 `.` / `-` → 返回 None（避免无意义的第二次网络调用）。
    """
    if "." in ticker:
        alt = ticker.replace(".", "-")
    elif "-" in ticker:
        alt = ticker.replace("-", ".")
    else:
        return None
    return alt if alt != ticker else None


def tool_company_facts(ticker: str) -> dict:
    """取公司公开财务事实（12 个固定字段，来自 yfinance）。

    返回: {"ticker", "facts": {...12 键...}, "asof": "<UTC 日期>", "source": "yfinance", "error": null}
    失败: {"ticker", "facts": {}, "source": "yfinance", "error": "<...>"}

    首次取不到时会用**替代符号**重试一次（#5：池里写 `BRK-B`，模型可能传 `BRK.B`）；
    成功时返回的 `ticker` 是**实际生效的符号**。
    """
    if not isinstance(ticker, str) or not _TICKER_RE.match(ticker):
        return {"ticker": str(ticker), "facts": {}, "source": "yfinance", "error": "invalid_ticker"}

    try:
        import yfinance  # noqa: F401  # 提前验证依赖（真实调用在 _yf_fetch 内）
    except ImportError as e:
        return {"ticker": ticker, "facts": {}, "source": "yfinance", "error": f"import_error: {e}"}

    try:
        facts = _yf_fetch(ticker)
        used_ticker = ticker

        # 符号回退（#5）——只在"有可替代写法"时多打一次网络
        if not facts:
            alt = _alt_symbol(ticker)
            if alt:
                alt_facts = _yf_fetch(alt)
                if alt_facts:
                    facts, used_ticker = alt_facts, alt

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
            "ticker": used_ticker,        # ← 实际生效的符号（可能是替代写法）
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
# --------------------------------------------------------------------------- #
# 工具 4：verify_macro_series（**独立实现**：刻意不复用 scan.py 的抓取链）
# --------------------------------------------------------------------------- #
# 为什么独立：scan.py 是本地宏观数据的产生者；若核验工具复用同一段代码，
# 同一个 bug 会被"复现"而不是"发现"（CPI 曾显示 334.98% 即为格式化 bug）。
# scan.py 还不可 import（模块级 sys.exit + 无 __main__ 守卫），故也不具备复用条件。
_MACRO_SERIES = {
    "CPI":      ("CPIAUCSL", "index"),
    "核心CPI":  ("CPILFESL", "index"),
    "失业率":   ("UNRATE",   "pct"),
    "核心PCE":  ("PCEPILFE", "index"),
}
_MACRO_YAHOO = {"10Y国债": "^TNX"}
_MACRO_LABELS = tuple(_MACRO_SERIES) + tuple(_MACRO_YAHOO)
_FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"


def _fred_csv_rows(sid: str, timeout: float = 10.0) -> list:
    """独立抓取 FRED CSV（无 API key）→ [(date, value)]，按日期升序。失败抛异常。"""
    import csv as _csv
    import io as _io
    from news_fetch_util import new_session
    r = new_session().get(_FRED_CSV.format(sid=sid), timeout=timeout)
    r.raise_for_status()
    rows = []
    for rec in _csv.DictReader(_io.StringIO(r.text)):
        date = (rec.get("DATE") or "").strip()
        raw = (rec.get(sid) or rec.get("VALUE") or "").strip()
        if not date or raw in ("", "."):
            continue                       # FRED 用 '.' 表示缺值
        try:
            rows.append((date, float(raw)))
        except ValueError:
            continue
    rows.sort(key=lambda x: x[0])
    return rows


def _yoy_from_rows(rows, last_date: str, last_val: float):
    """与「约 12 个月前」的读数比较（找不到返回 None）。"""
    from datetime import date as _d, timedelta as _td
    try:
        y, m, d = (int(x) for x in str(last_date)[:10].split("-"))
        target = _d(y, m, d) - _td(days=365)
    except Exception:
        return None
    best = None
    for date_s, val in rows:
        try:
            yy, mm, dd = (int(x) for x in date_s[:10].split("-"))
            cur = _d(yy, mm, dd)
        except Exception:
            continue
        if cur <= target and (best is None or cur > best[0]):
            best = (cur, val)
    if not best or not best[1]:
        return None
    return round((last_val / best[1] - 1) * 100, 2)


def _norm_tnx(v: float) -> float:
    """^TNX 的口径历史上是「收益率×10」，但 Yahoo 现价可能已是百分数。

    故只在数值明显偏大（>20）时才 /10 —— 两种口径都能得到正确的百分数。
    """
    return round(v / 10.0, 3) if v > 20 else round(v, 3)


def tool_verify_macro_series(label: str, *, timeout: float = 10.0) -> dict:
    """联网核验一条美国宏观指标的最新官方值（**独立抓取**，与 scan.py 刻意不同源/不同码）。

    返回: {"label","value","prev","yoy","asof","source","error"}
    失败: {"label", "value": None, "error": "<type>: <msg>"}"
    """
    if not isinstance(label, str) or label.strip() not in _MACRO_LABELS:
        return {"label": str(label), "value": None, "error": "unknown_label"}
    label = label.strip()
    try:
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if label in _MACRO_YAHOO:
            from portfolio_50000 import fetch_last_closes
            sym = _MACRO_YAHOO[label]
            row = (fetch_last_closes([sym]) or {}).get(sym) or {}
            cur = row.get("current")
            if cur is None:
                return {"label": label, "value": None, "error": "no_data"}
            return {"label": label, "value": _norm_tnx(float(cur)), "prev": None, "yoy": None,
                    "asof": today, "source": "Yahoo:^TNX (independent)", "error": None}
        sid, kind = _MACRO_SERIES[label]
        rows = _fred_csv_rows(sid, timeout=timeout)
        if not rows:
            return {"label": label, "value": None, "error": "no_data"}
        date_s, val = rows[-1]
        return {
            "label": label,
            "value": round(val, 3),
            "prev": round(rows[-2][1], 3) if len(rows) >= 2 else None,
            "yoy": _yoy_from_rows(rows, date_s, val) if kind == "index" else None,
            "asof": date_s[:10],
            "source": f"FRED:{sid} (independent)",
            "error": None,
        }
    except Exception as e:                                     # noqa: BLE001
        return {"label": label, "value": None, "error": f"{type(e).__name__}: {e}"}


# --------------------------------------------------------------------------- #
# 工具 5：verify_current_price（复用 portfolio_50000.fetch_last_closes）
# --------------------------------------------------------------------------- #
def tool_verify_current_price(ticker: str) -> dict:
    """取某只股票的当前市价，用于核验本地记录的价格是否过期。

    返回: {"ticker","price","extended","extended_time","asof","source","error"}
    失败: {"ticker", "price": None, "error": "<...>"}"
    """
    if not isinstance(ticker, str) or not _TICKER_RE.match(ticker):
        return {"ticker": str(ticker), "price": None, "error": "invalid_ticker"}
    try:
        from portfolio_50000 import fetch_last_closes
    except ImportError as e:
        return {"ticker": ticker, "price": None, "error": f"import_error: {e}"}
    try:
        used = ticker
        row = (fetch_last_closes([used]) or {}).get(used.upper()) or {}
        if not row:
            alt = _alt_symbol(ticker)                          # 复用 #5 的符号回退
            if alt:
                row = (fetch_last_closes([alt]) or {}).get(alt.upper()) or {}
                if row:
                    used = alt
        if not row or row.get("current") is None:
            return {"ticker": ticker, "price": None, "error": "no_data"}
        from datetime import datetime, timezone
        ext = row.get("extended")
        return {
            "ticker": used,
            "price": float(row["current"]),
            "extended": (float(ext) if ext is not None else None),
            "extended_time": row.get("extended_time") or "",
            "asof": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "source": "yfinance",
            "error": None,
        }
    except Exception as e:                                     # noqa: BLE001
        return {"ticker": ticker, "price": None, "error": f"{type(e).__name__}: {e}"}





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
    {
        "name": "verify_macro_series",
        "description": "联网核验一条美国宏观指标的最新官方值，用于交叉检查本地宏观面板的"
                       "数值是否过期或错误。返回最新值 / 上期值 / 同比 / 数据期。",
        "input_schema": {
            "type": "object",
            "properties": {
                "label": {"type": "string", "enum": ["CPI", "核心CPI", "失业率", "10Y国债", "核心PCE"]},
            },
            "required": ["label"],
        },
    },
    {
        "name": "verify_current_price",
        "description": "取某只股票的当前市价，用于核验本地记录的价格是否过期。",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "股票代码，如 CME"},
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
    "verify_macro_series": tool_verify_macro_series,
    "verify_current_price": tool_verify_current_price,
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
