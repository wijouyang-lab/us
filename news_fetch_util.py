#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新闻抓取的**公共纯函数层**（无模块级副作用、不依赖 scan.py）。

抽取自 `scan.py` 的以下逻辑（段 1A，行为保持不变）：
  · `get_robust_session()`      → `new_session()`
  · `_parse_rss_date()`         → `parse_rss_date()`
  · `_news_age_tag()`           → `news_age_tag()`（`asof` 可显式注入）
  · `_rss_search_google()`      → `rss_search_google()`（返回**结构化 dict**）
  · `get_stock_news_snapshot()` → `fetch_ticker_news()`（返回**结构化 dict**）

设计要点
--------
1. **零导入期副作用**：只 import 标准库 + `requests`；不读环境变量、不发请求、不写文件。
   （对比 `scan.py` 导入即 `_ai_preflight()` + `update_version_marker()` + 周末 `sys.exit(0)`，
   故 `skills/serenity_tools.py` 必须用本模块而不是 import scan。）
2. **上下文显式注入**：原逻辑里的 `datetime.now(utc)` 与 `RUN_ASOF_UTC` 改为参数
   （`asof` / `since`），调用方自己决定"现在"与"昨收分界"。
3. **向后兼容**：返回的 dict 里带 `line` 字段 = scan.py 原来那行**预格式化字符串**，
   因此 scan 侧只需 `[d["line"] for d in ...]` 即可保持输出**逐字节不变**。
4. **不依赖 pandas**：原 `_previous_close_cutoff_us()` 留在 scan.py（它用 pd.Timestamp），
   由 scan 计算后作为 `since` 注入。

安全护栏（供 tool executor 使用）
--------------------------------
· 端点**固定**（Google News RSS / Yahoo Finance RSS），不接受任意 URL；
· 每个请求 `timeout` 参数可控（默认与原实现一致）；
· 返回条数由 `max_items` 封顶。
"""
from __future__ import annotations

import datetime
import email.utils
import re
import time
import xml.etree.ElementTree as ET
from typing import Any, Iterable, Optional
from zoneinfo import ZoneInfo

import requests

# 与 scan.py:151 一致
US_TZ = ZoneInfo("America/New_York")

# 与 scan.py:272-274 完全一致的请求头
_SESSION_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
    "Referer": "https://finance.yahoo.com/",
}

# 与 scan.py:519 一致：只保留 asof 前 72 小时内的新闻
_NEWS_LOOKBACK_HOURS = 72


def new_session() -> requests.Session:
    """构造带固定请求头的 Session（等价于 scan.py:269 get_robust_session()）。"""
    session = requests.Session()
    session.headers.update(_SESSION_HEADERS)
    return session


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def parse_rss_date(date_str: Any) -> Optional[datetime.datetime]:
    """解析 RSS pubDate → UTC datetime；失败返回 None（等价于 scan.py:279）。"""
    if not date_str:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(str(date_str).strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone.utc)
    except Exception:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.datetime.strptime(
                    str(date_str).strip()[:19], fmt
                ).replace(tzinfo=datetime.timezone.utc)
            except Exception:
                pass
    return None


def news_age_tag(dt: Optional[datetime.datetime],
                 asof: Optional[datetime.datetime] = None) -> Optional[str]:
    """按 `asof` 计算年龄权重标签（等价于 scan.py:296 `_news_age_tag`）。

    `asof=None` 时取当前 UTC 时刻 —— 这正是 scan.py 原实现的语义，
    故 scan 侧无需改动即可保持逐字节一致；新调用方应显式传 `asof`。
    """
    if dt is None:
        return "[时间未知]"
    now = asof or _utcnow()
    delta_hours = (now - dt).total_seconds() / 3600
    if delta_hours <= 6:
        return "[🔥今日最新-权重最高]"
    if delta_hours <= 24:
        return "[📰今日-高权重]"
    if delta_hours <= 48:
        return "[📄昨日-中等权重]"
    if delta_hours <= 72:
        return "[📑前日-低权重]"
    return None


def _fmt_google_ts(dt: Optional[datetime.datetime]) -> str:
    """等价于 scan.py:1389 的时间片段。"""
    return dt.astimezone(US_TZ).strftime("%m-%d %H:%M") if dt else "时间未知"


def _rss_items(url: str, session: requests.Session, timeout: float) -> Iterable[ET.Element]:
    """取一次 RSS 并返回 <item> 列表（不发请求之外的事）。"""
    resp = session.get(url, timeout=timeout)
    resp.raise_for_status()
    return ET.fromstring(resp.content).findall(".//item")


def rss_search_google(query: str, *, max_items: int = 8, timeout: float = 10.0) -> list[dict]:
    """Google News RSS 搜索，返回**结构化**结果（等价于 scan.py:1370 的抓取逻辑）。

    返回（按时间倒序，最多 `max_items` 条）::

        [{"title", "link", "date_str", "date_dt", "source": "Google News",
          "age_tag", "line"}]

    其中 `line` 与 scan.py 原实现逐字节一致：``f"{tag}[Google News] {ts} - {title}"``。
    与原实现一致：标题为空或 age_tag 为 None（>72h）的条目**跳过**；503 重试 1 次后仍失败返回 []。
    """
    session = new_session()
    q = requests.utils.quote(query)
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    out: list[tuple] = []
    last_err = None
    for attempt in range(2):  # 503 时重试 1 次
        try:
            for item in list(_rss_items(url, session, timeout))[:max_items * 2]:
                title = (item.findtext("title", default="") or "").strip()
                pub = item.findtext("pubDate", default="")
                dt = parse_rss_date(pub)
                tag = news_age_tag(dt)
                if not title or tag is None:
                    continue
                ts = _fmt_google_ts(dt)
                out.append((dt, {
                    "title": title,
                    "link": (item.findtext("link", default="") or "").strip(),
                    "date_str": ts,
                    "date_dt": dt,
                    "source": "Google News",
                    "age_tag": tag,
                    "line": f"{tag}[Google News] {ts} - {title}",
                }))
            break  # 成功则跳出重试
        except Exception as e:
            last_err = e
            if attempt == 0:
                time.sleep(2)  # 503 时等待 2 秒后重试
    if not out and last_err:
        print(f"   ⚠️ Google News 查询失败 {query}: {last_err}")
    out.sort(key=lambda x: x[0] or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),
             reverse=True)
    return [x[1] for x in out[:max_items]]


# 与 scan.py:501-505 完全一致的三个 RSS 源
_TICKER_RSS_SOURCES = (
    ("Yahoo", "https://feeds.finance.yahoo.com/rss/2.0/headline?s={tk}&region=US&lang=en-US"),
    ("Google News", "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"),
    ("Reuters Search", "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"),
)


def fetch_ticker_news(ticker: str, *, max_items: int = 6, timeout: float = 8.0,
                      asof: Optional[datetime.datetime] = None,
                      since: Optional[datetime.datetime] = None,
                      age_asof: Optional[datetime.datetime] = None) -> list[dict]:
    """取某只股票的新闻（等价于 scan.py:493 `get_stock_news_snapshot` 的抓取逻辑）。

    返回（按时间倒序、按标题去重、最多 `max_items` 条）::

        [{"title", "link", "date_str", "date_dt", "source", "age_tag",
          "after_close", "line"}]

    · `asof`  — 代替 scan.py 的模块级 `RUN_ASOF_UTC`：> asof+1min 或 < asof-72h 的条目跳过；
    · `since` — 「昨收后」分界（scan.py 用 `_previous_close_cutoff_us()` 计算）→ `after_close`；
    · `line`  — 与 scan.py 逐字节一致：``f"{bucket}{age}[{source}] {ts} — {title}"``。
    """
    now = asof or _utcnow()
    cutoff = now + datetime.timedelta(minutes=1)
    floor = now - datetime.timedelta(hours=_NEWS_LOOKBACK_HOURS)
    ticker = str(ticker).strip().upper()
    session = new_session()
    rows = []
    for source_name, tpl in _TICKER_RSS_SOURCES:
        if "{tk}" in tpl:
            url = tpl.format(tk=ticker)
        else:
            keyword = ticker + (" stock" if source_name == "Google News" else " site:reuters.com")
            url = tpl.format(q=requests.utils.quote(keyword))
        try:
            for item in list(_rss_items(url, session, timeout))[:12]:
                title = (item.findtext("title", default="") or "").strip()
                dt = parse_rss_date(item.findtext("pubDate", default=""))
                if not title or not dt:
                    continue
                if dt > cutoff or dt < floor:
                    continue
                rows.append({
                    "title": title,
                    "link": (item.findtext("link", default="") or "").strip(),
                    "dt": dt,
                    "source": source_name,
                    "after_close": bool(since is not None and dt >= since),
                })
        except Exception:
            continue

    rows.sort(key=lambda x: x["dt"], reverse=True)
    out, seen = [], set()
    for r in rows:
        # 与 scan.py 原实现逐字节一致的去重键（注意：不能用 str.isalnum() —— 那会保留
        # Unicode 字母/数字，与 scan 的 [^a-z0-9] 语义不同）
        key = re.sub(r"[^a-z0-9]+", "", r["title"].lower())
        if key in seen:
            continue
        seen.add(key)
        # age_asof 默认 None = 取当前 UTC —— 与 scan.py 原 `_news_age_tag(r['dt'])` 一致；
        # 注意它与 `asof`（窗口/截止点，scan 传 RUN_ASOF_UTC）是**两个不同的时钟**，故分开传参。
        age = news_age_tag(r["dt"], asof=age_asof) or "[较旧]"
        bucket = "[🆕昨收后]" if r["after_close"] else "[📄历史背景]"
        ts = r["dt"].astimezone(US_TZ).strftime("%m-%d %H:%M ET")
        out.append({
            "title": r["title"],
            "link": r["link"],
            "date_str": ts,
            "date_dt": r["dt"],
            "source": r["source"],
            "age_tag": age,
            "after_close": r["after_close"],
            "line": f"{bucket}{age}[{r['source']}] {ts} — {r['title']}",
        })
        if len(out) >= max_items:
            break
    return out
