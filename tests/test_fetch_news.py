"""fetch_news.py 单元测试（全部 mock，绝不调用真实 Finnhub API）。

覆盖：
  1. key 缺失 → 返回 error + 空结构（不崩）
  2. mock API 成功 → 正确解析 market_news + ticker_news
  3. mock 单只 ticker 失败 → 其他 ticker 仍正常
  4. mock 429 → 重试逻辑生效（最多 3 次后成功）
  5. R1：无数据 → 不写文件
  6. 不硬编码绝对日期（from/to 动态派生）
"""
from datetime import date

import pytest
import urllib.error

import dashboard.fetch_news as fn


# ------------------------------------------------------------------ helpers
def _item(head="H", src="S", url="u", ts=1700000000, summary="sm"):
    return {"headline": head, "source": src, "url": url, "datetime": ts, "summary": summary}


def _market_get(market_items, ticker_map):
    """根据 URL 返回对应数据的 http_get 替身。"""
    def fake(url, api_key, retries=3, sleep_fn=None):
        if "category=general" in url:
            return list(market_items)
        # company-news
        for sym, items in ticker_map.items():
            if f"symbol={sym}" in url:
                return list(items)
        return []
    return fake


# ------------------------------------------------------------------ 1. key 缺失
def test_missing_key_writes_error_structure(tmp_path, monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    out = tmp_path / "news_data.json"
    fn.main(["--tickers", "A,B"], out_path=out)
    assert out.exists()
    d = __import__("json").loads(out.read_text(encoding="utf-8"))
    assert d["error"] == "FINNHUB_API_KEY not set"
    assert d["market_news"] == []
    assert d["ticker_news"] == {}


# ------------------------------------------------------------------ 2. 成功解析
def test_success_parses_market_and_ticker(tmp_path, monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "dummy")
    monkeypatch.setattr(fn.time, "sleep", lambda *a, **k: None)
    fake = _market_get([_item("M1")], {"A": [_item("CA")], "B": [_item("CB")]})
    monkeypatch.setattr(fn, "http_get", fake)
    out = tmp_path / "news_data.json"
    fn.main(["--tickers", "A,B"], out_path=out)
    d = __import__("json").loads(out.read_text(encoding="utf-8"))
    assert d["error"] is None
    assert len(d["market_news"]) == 1 and d["market_news"][0]["headline"] == "M1"
    assert d["ticker_news"]["A"][0]["headline"] == "CA"
    assert d["ticker_news"]["B"][0]["headline"] == "CB"
    assert d["schema_version"] == "news.v1"


# ------------------------------------------------------------------ 3. 单只 ticker 失败不影响其他
def test_single_ticker_failure_isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "dummy")
    monkeypatch.setattr(fn.time, "sleep", lambda *a, **k: None)

    def fake(url, api_key, retries=3, sleep_fn=None):
        if "category=general" in url:
            return [_item("M1")]
        if "symbol=BAD" in url:
            raise fn.FinnhubError("boom")
        return [_item("OK")]

    monkeypatch.setattr(fn, "http_get", fake)
    out = tmp_path / "news_data.json"
    fn.main(["--tickers", "A,BAD"], out_path=out)
    d = __import__("json").loads(out.read_text(encoding="utf-8"))
    assert d["ticker_news"]["A"][0]["headline"] == "OK"
    assert d["ticker_news"]["BAD"] == []          # 该 ticker 留空
    assert "BAD" in (d["error"] or "")             # 错误被记录


# ------------------------------------------------------------------ 4. 429 重试（mock 网络层 URLOPEN，验证 http_get 内部重试）
def test_429_retry_then_success(tmp_path, monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "dummy")
    market_calls = {"n": 0}
    sleeps = {"n": 0}

    class FakeResp:
        def __init__(self, data):
            self._d = data.encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def read(self):
            return self._d

    def fake_sleep(s):
        sleeps["n"] += 1

    def fake_urlopen(req, timeout=15):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if "category=general" in url:
            market_calls["n"] += 1
            if market_calls["n"] <= 2:
                raise urllib.error.HTTPError("http://x", 429, "rate", None, None)
            return FakeResp(__import__("json").dumps([_item("M1")]))
        return FakeResp(__import__("json").dumps([_item("T1")]))   # 个股

    monkeypatch.setattr(fn, "URLOPEN", fake_urlopen)
    monkeypatch.setattr(fn.time, "sleep", fake_sleep)
    out = tmp_path / "news_data.json"
    fn.main(["--tickers", "A"], out_path=out)     # 市场（含 429 重试）+ 1 个股
    d = __import__("json").loads(out.read_text(encoding="utf-8"))
    assert len(d["market_news"]) == 1             # 重试后成功
    assert d["ticker_news"]["A"][0]["headline"] == "T1"
    assert market_calls["n"] == 3                 # 前 2 次 429 + 第 3 次成功
    assert sleeps["n"] >= 2                        # 退避 sleep 被调用


# ------------------------------------------------------------------ 5. R1 无数据不写文件
def test_r1_no_data_skips_write(tmp_path, monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "dummy")
    monkeypatch.setattr(fn.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(fn, "http_get", lambda url, api_key, retries=3, sleep_fn=None: [])
    out = tmp_path / "news_data.json"
    fn.main(["--no-market", "--tickers", ""], out_path=out)
    assert not out.exists()                       # R1：无内容不落文件


# ------------------------------------------------------------------ 6. 不硬编码绝对日期
def test_dates_derived_dynamically(tmp_path, monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "dummy")
    monkeypatch.setattr(fn.time, "sleep", lambda *a, **k: None)
    captured = {}

    def fake(url, api_key, retries=3, sleep_fn=None):
        if "symbol=" in url:
            captured["url"] = url
            return [_item("CA")]
        return []

    monkeypatch.setattr(fn, "http_get", fake)
    out = tmp_path / "news_data.json"
    fn.main(["--no-market", "--tickers", "A"], out_path=out)

    today = date.today().strftime("%Y-%m-%d")
    week_ago = (date.today() - __import__("datetime").timedelta(days=7)).strftime("%Y-%m-%d")
    assert "from=" + week_ago in captured["url"]
    assert "to=" + today in captured["url"]
