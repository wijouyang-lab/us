#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`news_fetch_util` 的格式契约 + 边界单测（段 1A）。

全部 **不联网**：用 monkeypatch 替换 `requests.Session.get` 返回伪造 RSS。

设计要点
--------
· **日期一律相对 / 显式注入**：绝不写死 "2026-10-13" 之类的绝对日期 ——
  否则测试换一天跑就会因为 age_tag 为 None（>72h 被跳过）而失败。
· **时间在两个时钟分开注入**：`asof`（窗口/截止点）与 `age_asof`（年龄标签），
  与 scan.py 原实现（`RUN_ASOF_UTC` vs `now()`）保持一致。
· 覆盖 `line` 字段的**两种模板**（这是 scan 侧输出逐字节不变的契约）：
    Google: f"{tag}[Google News] {ts} - {title}"
    Ticker: f"{bucket}{age}[{source}] {ts} — {title}"
"""
import datetime
import inspect

import pytest
import requests

import news_fetch_util as u

UTC = datetime.timezone.utc
FIXED = datetime.datetime(2026, 10, 13, 12, 0, 0, tzinfo=UTC)


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
class _FakeResp:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        return None


def _rss(items) -> str:
    """items: [(title, link, rfc822_pubdate)] → RSS XML"""
    body = "".join(
        f"<item><title>{t}</title><link>{l}</link><pubDate>{p}</pubDate></item>"
        for t, l, p in items
    )
    return f'<?xml version="1.0"?><rss version="2.0"><channel>{body}</channel></rss>'


def _rfc(dt: datetime.datetime) -> str:
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")


def _install(monkeypatch, responder):
    """替换 requests.Session.get；返回记录到的 URL 列表。"""
    calls = []

    def _get(self, url, timeout=None, **kwargs):  # noqa: ANN001
        calls.append((url, timeout))
        return _FakeResp(responder(url).encode("utf-8"))

    monkeypatch.setattr(requests.Session, "get", _get)
    monkeypatch.setattr(u.time, "sleep", lambda *_: None)   # 去掉 503 重试的 2 秒等待
    return calls


# --------------------------------------------------------------------------- #
# 1) 基础纯函数
# --------------------------------------------------------------------------- #
def test_new_session_headers_match_scan(monkeypatch):
    s = u.new_session()
    assert isinstance(s, requests.Session)
    assert s.headers["User-Agent"].startswith("Mozilla/5.0 (Windows NT 10.0")
    assert s.headers["Accept-Language"] == "en-US,en;q=0.9,zh-CN;q=0.8"
    assert s.headers["Referer"] == "https://finance.yahoo.com/"


def test_parse_rss_date_formats():
    assert u.parse_rss_date(None) is None
    assert u.parse_rss_date("") is None
    assert u.parse_rss_date("not a date") is None
    assert u.parse_rss_date("Mon, 13 Oct 2026 09:12:00 GMT") == \
        datetime.datetime(2026, 10, 13, 9, 12, tzinfo=UTC)
    # 回退格式
    assert u.parse_rss_date("2026-10-13 09:12:00") == \
        datetime.datetime(2026, 10, 13, 9, 12, tzinfo=UTC)
    assert u.parse_rss_date("2026-10-13") == \
        datetime.datetime(2026, 10, 13, 0, 0, tzinfo=UTC)


@pytest.mark.parametrize("hours,expected", [
    (0.5, "[🔥今日最新-权重最高]"),
    (6.0, "[🔥今日最新-权重最高]"),      # 边界：<=6
    (6.1, "[📰今日-高权重]"),
    (24.0, "[📰今日-高权重]"),           # 边界：<=24
    (24.1, "[📄昨日-中等权重]"),
    (48.0, "[📄昨日-中等权重]"),         # 边界：<=48
    (48.1, "[📑前日-低权重]"),
    (72.0, "[📑前日-低权重]"),           # 边界：<=72
    (72.1, None),                        # 越界 → None
])
def test_news_age_tag_boundaries(hours, expected):
    dt = FIXED - datetime.timedelta(hours=hours)
    assert u.news_age_tag(dt, asof=FIXED) == expected


def test_news_age_tag_none_and_default_asof():
    assert u.news_age_tag(None) == "[时间未知]"
    # asof 缺省 = 当前 UTC（scan.py 原语义）：刚发生的事件必为「最新」
    assert u.news_age_tag(datetime.datetime.now(UTC)) == "[🔥今日最新-权重最高]"


# --------------------------------------------------------------------------- #
# 2) rss_search_google
# --------------------------------------------------------------------------- #
def test_rss_search_google_shape_and_line_format(monkeypatch):
    fresh = FIXED - datetime.timedelta(hours=1)
    xml = _rss([("Fed signals rate path shift - Reuters", "https://example.com/a", _rfc(fresh))])
    calls = _install(monkeypatch, lambda url: xml)

    got = u.rss_search_google("Fed", max_items=8)
    assert len(got) == 1
    it = got[0]
    assert it["title"] == "Fed signals rate path shift - Reuters"
    assert it["link"] == "https://example.com/a"
    assert it["source"] == "Google News"
    assert it["age_tag"] == "[🔥今日最新-权重最高]"
    assert it["date_dt"] == fresh
    ts = fresh.astimezone(u.US_TZ).strftime("%m-%d %H:%M")
    # ← scan 侧输出的逐字节契约
    assert it["line"] == f"[🔥今日最新-权重最高][Google News] {ts} - Fed signals rate path shift - Reuters"
    # 端点固定 + 超时默认 10s + query 已编码
    url, timeout = calls[0]
    assert url.startswith("https://news.google.com/rss/search?q=Fed&")
    assert timeout == 10.0


def test_rss_search_google_skips_old_and_empty_title(monkeypatch):
    fresh = FIXED - datetime.timedelta(hours=2)
    old = FIXED - datetime.timedelta(hours=100)     # >72h → age_tag None → 跳过
    xml = _rss([
        ("", "https://example.com/empty", _rfc(fresh)),      # 空标题 → 跳过
        ("Too old - X", "https://example.com/old", _rfc(old)),
        ("Keep me - Y", "https://example.com/keep", _rfc(fresh)),
    ])
    _install(monkeypatch, lambda url: xml)
    got = u.rss_search_google("q")
    assert [i["title"] for i in got] == ["Keep me - Y"]


def test_rss_search_google_truncates_and_sorts_desc(monkeypatch):
    items = [(f"H{i} - S", f"https://example.com/{i}", _rfc(FIXED - datetime.timedelta(hours=i)))
             for i in range(1, 4)]
    _install(monkeypatch, lambda url: _rss(items))
    got = u.rss_search_google("q", max_items=2)
    assert len(got) == 2
    # 时间倒序：H1（1 小时前）在 H2（2 小时前）之前
    assert [i["title"] for i in got] == ["H1 - S", "H2 - S"]


def test_rss_search_google_failure_returns_empty_and_retries(monkeypatch):
    calls = []

    def _boom(url):
        calls.append(url)
        raise RuntimeError("503")

    _install(monkeypatch, _boom)
    assert u.rss_search_google("q") == []
    assert len(calls) == 2          # 重试 1 次后放弃（原实现行为）


# --------------------------------------------------------------------------- #
# 3) fetch_ticker_news
# --------------------------------------------------------------------------- #
def _ticker_responder(yahoo, gnews, reuters=()):
    def _r(url: str) -> str:
        if "feeds.finance.yahoo.com" in url:
            return _rss(yahoo)
        if "reuters" in url.lower():
            return _rss(reuters)
        return _rss(gnews)
    return _r


def test_fetch_ticker_news_shape_and_line_format(monkeypatch):
    fresh = FIXED - datetime.timedelta(hours=3)
    _install(monkeypatch, _ticker_responder(
        [("Yahoo headline - Y", "https://y/1", _rfc(fresh))], [], []))
    got = u.fetch_ticker_news("aapl", max_items=6, asof=FIXED, age_asof=FIXED)
    assert len(got) == 1
    it = got[0]
    assert it["source"] == "Yahoo"
    assert it["age_tag"] == "[🔥今日最新-权重最高]"
    assert it["after_close"] is False
    ts = fresh.astimezone(u.US_TZ).strftime("%m-%d %H:%M ET")
    # ← scan 侧输出的逐字节契约
    assert it["line"] == f"[📄历史背景][🔥今日最新-权重最高][Yahoo] {ts} — Yahoo headline - Y"


def test_fetch_ticker_news_after_close_bucket(monkeypatch):
    fresh = FIXED - datetime.timedelta(hours=3)
    since = FIXED - datetime.timedelta(hours=5)
    _install(monkeypatch, _ticker_responder(
        [("After close - Y", "https://y/1", _rfc(fresh))], [], []))
    got = u.fetch_ticker_news("AAPL", asof=FIXED, since=since, age_asof=FIXED)
    assert got[0]["after_close"] is True
    assert got[0]["line"].startswith("[🆕昨收后]")


def test_fetch_ticker_news_window_filters_future_and_old(monkeypatch):
    _install(monkeypatch, _ticker_responder([
        ("Future - Y", "https://y/1", _rfc(FIXED + datetime.timedelta(hours=2))),  # > asof+1min
        ("Old - Y", "https://y/2", _rfc(FIXED - datetime.timedelta(hours=73))),    # < asof-72h
        ("Keep - Y", "https://y/3", _rfc(FIXED - datetime.timedelta(hours=5))),
    ], [], []))
    got = u.fetch_ticker_news("AAPL", asof=FIXED, age_asof=FIXED)
    assert [i["title"] for i in got] == ["Keep - Y"]


def test_fetch_ticker_news_dedupes_across_sources(monkeypatch):
    same = FIXED - datetime.timedelta(hours=4)
    _install(monkeypatch, _ticker_responder(
        [("Same Headline - X", "https://y/1", _rfc(same))],
        [("Same Headline - X", "https://g/1", _rfc(same))],   # 同标题、不同来源 → 去重
    ))
    got = u.fetch_ticker_news("AAPL", asof=FIXED, age_asof=FIXED)
    assert len(got) == 1
    assert got[0]["source"] == "Yahoo"      # 保留排序后首条


def test_fetch_ticker_news_truncates_max_items(monkeypatch):
    items = [(f"H{i} - Y", f"https://y/{i}", _rfc(FIXED - datetime.timedelta(hours=i)))
             for i in range(1, 6)]
    _install(monkeypatch, _ticker_responder(items, [], []))
    got = u.fetch_ticker_news("AAPL", max_items=2, asof=FIXED, age_asof=FIXED)
    assert len(got) == 2
    assert [i["title"] for i in got] == ["H1 - Y", "H2 - Y"]


def test_fetch_ticker_news_timeout_default_is_8s(monkeypatch):
    calls = _install(monkeypatch, _ticker_responder(
        [("H - Y", "https://y/1", _rfc(FIXED))], [], []))
    u.fetch_ticker_news("AAPL", asof=FIXED, age_asof=FIXED)
    assert all(t == 8.0 for _, t in calls)
    assert len(calls) == 3          # Yahoo / Google News / Reuters 三个源都试


# --------------------------------------------------------------------------- #
# 4) 安全护栏：公共 API 不接受任意 URL
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("fn", [u.rss_search_google, u.fetch_ticker_news,
                                u.parse_rss_date, u.news_age_tag, u.new_session])
def test_public_api_has_no_url_parameter(fn):
    params = set(inspect.signature(fn).parameters)
    assert "url" not in params, f"{fn.__name__} 不应接受任意 URL"
    assert "endpoint" not in params
