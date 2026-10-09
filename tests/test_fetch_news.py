"""fetch_news.py 单元测试（全部 mock，绝不调用真实 Finnhub API）。

覆盖：
  1. key 缺失 → 返回 error + 空结构（不崩）
  2. mock API 成功 → 正确解析 market_news + ticker_news
  3. mock 单只 ticker 失败 → 其他 ticker 仍正常
  4. mock 429 → 重试逻辑生效（最多 3 次后成功）
  5. R1：无数据 → 不写文件
  6. 不硬编码绝对日期（from/to 动态派生）
  7. 翻译批量调用（mock client，一次 API 调用多条）
  8. 缓存命中 → 跳过翻译调用
  9. sentiment 归一化解析
  10. 翻译失败不阻断（headline_cn 留空）
  11. rationale：AI 含 → 正确解析；缺 → 留空不影响翻译
  12. 前端 newsRow：rationale 非空渲染该行、为空不渲染
"""
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
import urllib.error

import dashboard.fetch_news as fn

REPO_ROOT = Path(__file__).resolve().parent.parent


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


# ------------------------------------------------------------------ 7. 翻译批量调用（mock client）
def test_translate_headlines_batch_mock():
    out_json = json.dumps([
        {"headline": "Apple beats earnings", "headline_cn": "苹果业绩超预期", "sentiment": "bullish"},
        {"headline": "Fed raises rates", "headline_cn": "美联储加息", "sentiment": "bearish"},
    ])

    class FakeResp:
        def __init__(self, text):
            self.output_text = text

    class FakeMessages:
        def __init__(self):
            self.recorded = None

        def create(self, **kw):
            self.recorded = kw
            return FakeResp(out_json)

    class FakeClient:
        def __init__(self):
            self.api_key = "dummy"
            self.messages = FakeMessages()

    c = FakeClient()
    res = fn.translate_headlines(["Apple beats earnings", "Fed raises rates"], client=c)
    assert res["Apple beats earnings"]["headline_cn"] == "苹果业绩超预期"
    assert res["Apple beats earnings"]["sentiment"] == "bullish"
    assert res["Fed raises rates"]["sentiment"] == "bearish"
    # 批量：一次 API 调用、单条 user message、包含全部标题
    assert len(c.messages.recorded["messages"]) == 1
    assert c.messages.recorded["model"] == "claude-opus-5-5"
    content = c.messages.recorded["messages"][0]["content"]
    assert "Apple beats earnings" in content and "Fed raises rates" in content


# ------------------------------------------------------------------ 8. 缓存命中 → 跳过翻译
def test_cache_hit_skips_translate(tmp_path, monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "dummy")
    monkeypatch.setattr(fn.time, "sleep", lambda *a, **k: None)
    fake = _market_get([_item("M1")], {"A": [_item("CA")]})
    monkeypatch.setattr(fn, "http_get", fake)

    cache = tmp_path / "cache.json"
    calls = {"n": 0}

    def fake_translate(headlines):
        calls["n"] += 1
        return {h: {"headline_cn": "译:" + h, "sentiment": "neutral"} for h in headlines}

    # 第一次：无缓存 → 调用一次
    fn.run("dummy", ["A"], True, out_path=tmp_path / "o1.json",
           position_tickers=["A"], translate_fn=fake_translate, cache_path=cache)
    assert calls["n"] == 1

    # 第二次：全部命中缓存 → 不再调用
    calls["n"] = 0
    fn.run("dummy", ["A"], True, out_path=tmp_path / "o2.json",
           position_tickers=["A"], translate_fn=fake_translate, cache_path=cache)
    assert calls["n"] == 0

    d = json.loads((tmp_path / "o2.json").read_text(encoding="utf-8"))
    assert d["market_news"][0]["headline_cn"] == "译:M1"
    assert d["market_news"][0]["sentiment"] == "neutral"
    assert d["ticker_news"]["A"][0]["headline_cn"] == "译:CA"


# ------------------------------------------------------------------ 9. sentiment 归一化解析
def test_sentiment_normalization():
    assert fn._norm_sentiment("BULLISH") == "bullish"
    assert fn._norm_sentiment("Bearish") == "bearish"
    assert fn._norm_sentiment("neutral") == "neutral"
    assert fn._norm_sentiment("weird") == "neutral"
    assert fn._norm_sentiment(None) == "neutral"
    assert fn._norm_sentiment("") == "neutral"


# ------------------------------------------------------------------ 10. 翻译失败不阻断
def test_translation_failure_does_not_block(tmp_path, monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "dummy")
    monkeypatch.setattr(fn.time, "sleep", lambda *a, **k: None)
    fake = _market_get([_item("M1")], {"A": [_item("CA")]})
    monkeypatch.setattr(fn, "http_get", fake)

    def boom(headlines):
        raise RuntimeError("translation down")

    fn.run("dummy", ["A"], True, out_path=tmp_path / "o.json",
           position_tickers=["A"], translate_fn=boom, cache_path=tmp_path / "c.json")
    d = json.loads((tmp_path / "o.json").read_text(encoding="utf-8"))
    assert d["market_news"][0]["headline"] == "M1"          # 抓取不受影响
    assert "headline_cn" not in d["market_news"][0]          # R1 留空
    assert "sentiment" not in d["market_news"][0]


# ------------------------------------------------------------------ 11. rationale 解析（AI 含 / 缺）
def _fake_client_with(out_json):
    class FakeResp:
        def __init__(self, text):
            self.output_text = text

    class FakeMessages:
        def create(self, **kw):
            return FakeResp(out_json)

    class FakeClient:
        def __init__(self):
            self.api_key = "dummy"
            self.messages = FakeMessages()

    return FakeClient()


def test_translate_headlines_with_rationale():
    out_json = json.dumps([
        {"headline": "Fed signals rate cut", "headline_cn": "美联储释放降息信号",
         "sentiment": "bullish", "rationale": "降息预期升温 → 流动性宽松利好股市"},
    ])
    res = fn.translate_headlines(["Fed signals rate cut"], client=_fake_client_with(out_json))
    item = res["Fed signals rate cut"]
    assert item["headline_cn"] == "美联储释放降息信号"
    assert item["sentiment"] == "bullish"
    assert item["rationale"] == "降息预期升温 → 流动性宽松利好股市"   # 正确解析


def test_translate_headlines_missing_rationale():
    out_json = json.dumps([
        {"headline": "Fed signals rate cut", "headline_cn": "美联储释放降息信号",
         "sentiment": "bullish"},
    ])
    res = fn.translate_headlines(["Fed signals rate cut"], client=_fake_client_with(out_json))
    item = res["Fed signals rate cut"]
    assert item["headline_cn"] == "美联储释放降息信号"   # 翻译不受影响
    assert item["sentiment"] == "bullish"
    assert item["rationale"] == ""                        # 缺 rationale → 留空


def test_norm_rationale_truncates_overlong():
    long = "x" * 31
    assert fn._norm_rationale(long) == ""        # 超 30 字 → 留空（格式错）
    assert fn._norm_rationale("正常理由") == "正常理由"
    assert fn._norm_rationale(None) == ""
    assert fn._norm_rationale("") == ""


def test_rationale_injected_into_news_data(tmp_path, monkeypatch):
    """端到端：含 rationale 的翻译应落到 news_data.json 相应条目。"""
    monkeypatch.setenv("FINNHUB_API_KEY", "dummy")
    monkeypatch.setattr(fn.time, "sleep", lambda *a, **k: None)
    fake = _market_get([_item("Fed signals rate cut")], {})
    monkeypatch.setattr(fn, "http_get", fake)

    def fake_translate(headlines):
        return {h: {"headline_cn": "美联储释放降息信号", "sentiment": "bullish",
                    "rationale": "降息预期升温 → 流动性宽松利好股市"} for h in headlines}

    out = tmp_path / "o.json"
    fn.run("dummy", [], True, out_path=out, position_tickers=[],
           translate_fn=fake_translate, cache_path=tmp_path / "c.json")
    d = json.loads(out.read_text(encoding="utf-8"))
    m = d["market_news"][0]
    assert m["headline_cn"] == "美联储释放降息信号"
    assert m["rationale"] == "降息预期升温 → 流动性宽松利好股市"


# ------------------------------------------------------------------ 12. 前端 newsRow 渲染（node 验证，不改动磁盘 app.js）
def test_news_row_rationale_render(tmp_path):
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    # 内存中：移除 boot() 启动、并暴露 newsRow 供断言（磁盘文件不变）
    transformed = app_js.replace("\n  boot();\n", "\n  globalThis.__newsRow = newsRow;\n")
    assert "globalThis.__newsRow" in transformed, "未能注入 newsRow 暴露钩子"
    harness = (
        "globalThis.document={addEventListener(){},querySelectorAll(){return[]},"
        "getElementById(){return null}};\n"
        "globalThis.window={addEventListener(){}};\n"
        "globalThis.fetch=()=>Promise.resolve({json:()=>Promise.resolve({})});\n"
        "globalThis.$=()=>({innerHTML:'',textContent:'',map:()=>[],forEach:()=>[]});\n"
    )
    tail = (
        "\nconst r1 = globalThis.__newsRow({headline:'Fed signals cut',"
        "headline_cn:'美联储释放降息信号',sentiment:'bullish',"
        "rationale:'降息预期升温 → 流动性宽松利好股市'});\n"
        "const r2 = globalThis.__newsRow({headline:'X',headline_cn:'Y',sentiment:'neutral'});\n"
        "console.log(JSON.stringify({withRationale: r1.includes('news-rationale'),"
        "withoutRationale: r2.includes('news-rationale')}));\n"
    )
    js = tmp_path / "harness.js"
    js.write_text(harness + transformed + tail, encoding="utf-8")
    proc = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, f"node 执行失败：{proc.stderr}"
    import json as _json
    result = _json.loads(proc.stdout.strip().splitlines()[-1])
    assert result["withRationale"] is True     # rationale 非空 → 渲染该行
    assert result["withoutRationale"] is False  # rationale 为空 → 不渲染该行


# ------------------------------------------------------------------ 13-14. 缓存完整性：缺 rationale 触发重译
def test_cache_entry_without_rationale_triggers_retranslate(tmp_path, monkeypatch):
    """旧缓存（无 rationale 键）→ 视为未命中 → 该 headline 被重译补全。"""
    monkeypatch.setenv("FINNHUB_API_KEY", "dummy")
    monkeypatch.setattr(fn.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(fn, "http_get", _market_get([_item("M1")], {}))

    h = "M1"
    # 旧缓存：只有 headline_cn / sentiment，没有 rationale 键
    cache = {fn._headline_hash(h): {"headline_cn": "译:M1", "sentiment": "neutral"}}
    (tmp_path / "c.json").write_text(json.dumps(cache), encoding="utf-8")

    called = []
    def fake_translate(headlines):
        called.append(list(headlines))
        return {hh: {"headline_cn": "译:M1", "sentiment": "neutral",
                     "rationale": "重译补全理由"} for hh in headlines}

    fn.run("dummy", [], True, out_path=tmp_path / "o.json",
           position_tickers=[], translate_fn=fake_translate, cache_path=tmp_path / "c.json")
    # 关键断言：M1 被纳入重译请求（即视为未命中）
    assert h in [hh for batch in called for hh in batch]
    d = json.loads((tmp_path / "o.json").read_text(encoding="utf-8"))
    assert d["market_news"][0]["headline_cn"] == "译:M1"
    assert d["market_news"][0]["rationale"] == "重译补全理由"   # rationale 已补全


def test_cache_entry_with_rationale_empty_string_is_complete(tmp_path, monkeypatch):
    """新缓存（含 rationale 键，值为空串）→ 视为完整 → 不重译。"""
    monkeypatch.setenv("FINNHUB_API_KEY", "dummy")
    monkeypatch.setattr(fn.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(fn, "http_get", _market_get([_item("M1")], {}))

    h = "M1"
    # 新缓存：含 rationale 键（空串是合法的「AI 判定超长归一化」结果）
    cache = {fn._headline_hash(h): {"headline_cn": "译:M1", "sentiment": "neutral",
                                    "rationale": ""}}
    (tmp_path / "c.json").write_text(json.dumps(cache), encoding="utf-8")

    called = []
    def fake_translate(headlines):
        called.append(list(headlines))
        return {hh: {"headline_cn": "译:M1", "sentiment": "neutral",
                     "rationale": "X"} for hh in headlines}

    fn.run("dummy", [], True, out_path=tmp_path / "o.json",
           position_tickers=[], translate_fn=fake_translate, cache_path=tmp_path / "c.json")
    # 关键断言：M1 未被重译（缓存完整）
    assert called == [] or h not in [hh for batch in called for hh in batch]
    d = json.loads((tmp_path / "o.json").read_text(encoding="utf-8"))
    assert d["market_news"][0]["headline_cn"] == "译:M1"
    assert "rationale" not in d["market_news"][0]   # 空串 rationale 不注入
