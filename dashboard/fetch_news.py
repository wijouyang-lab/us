#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finnhub 新闻抓取脚本（Dashboard 金融新闻板块数据源）

设计原则
--------
1. **密钥只在环境变量**：FINNHUB_API_KEY 通过 os.environ.get 读取，代码中绝不出现真实 key 字符串。
2. **纯标准库**：仅用 urllib.request + json，不引入 finnhub-python / requests，避免新增依赖。
3. **两类数据**：
   - 市场级：GET /news?category=general（通用财经新闻）
   - 个股级：对传入 ticker 列表调用 GET /company-news?symbol=X&from=..&to=..
4. **限流保护**：免费档 ~60 calls/min；42 只 + 1 市场 = 43 calls；每次调用间隔 0.5s 防突发；
   遇 HTTP 429 指数退避重试（最多 3 次）。
5. **异常不阻断**：API 失败 → error 字段记录 + 写空数组；单只股票失败 → 该 ticker 留空；
   key 缺失 → error="FINNHUB_API_KEY not set" + 空结构。
6. **R1 原则**：成功抓取但无任何内容（无 ticker + 无市场，且非错误态）→ 不写文件，避免落空壳。
7. **可测试**：http_get / sleep 均可注入；main() 接受 out_path 覆盖，便于单测。

输出：dashboard/data/news_data.json
{
  "schema_version": "news.v1",
  "generated_at": "2026-10-08T...Z",
  "market_news": [ {"headline","source","url","datetime","summary"} ],
  "ticker_news": { "ADSK": [...], "ANET": [...] },
  "error": null
}
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# ------------------------------------------------------------------ 常量
BASE = Path(__file__).resolve().parent                 # .../dashboard
REPO_ROOT_DEFAULT = BASE.parent                        # .../ (仓库根)
DATA_DIR = BASE / "data"                              # .../dashboard/data
OUT_PATH_DEFAULT = DATA_DIR / "news_data.json"
UNIVERSE_PATH_DEFAULT = REPO_ROOT_DEFAULT / "dashboard" / "data" / "dashboard_data.json"

SCHEMA_VERSION = "news.v1"
FINNHUB_BASE = "https://finnhub.io/api/v1"
# 可注入的网络调用（测试可 monkeypatch fn.URLOPEN 以验证 429 重试等行为）
URLOPEN = urllib.request.urlopen
MARKET_ENDPOINT = f"{FINNHUB_BASE}/news?category=general"
SLEEP_BETWEEN = 0.5          # 调用间隔（秒），防突发踩限流
MAX_RETRIES = 3              # 429 重试上限
COMPANY_LOOKBACK_DAYS = 7    # 个股新闻回溯窗口

NEWS_FIELDS = ("headline", "source", "url", "datetime", "summary")

# ------------------------------------------------------------------ 翻译
TRANSLATE_MODEL = os.environ.get("GPT_MODEL") or "claude-opus-5-5"
MARKET_TRANSLATE_TOP = 10    # 市场新闻翻译条数（top N）
TICKER_TRANSLATE_TOP = 5     # 每只持仓翻译条数（top N）
TRANSLATION_CACHE_PATH = DATA_DIR / "news_translation_cache.json"
POSITIONS_PATH_DEFAULT = REPO_ROOT_DEFAULT / "portfolio_50000_positions.csv"
_VALID_SENTIMENT = {"bullish", "bearish", "neutral"}


class FinnhubError(Exception):
    """抓取层统一异常（网络/限流耗尽/解析失败）。"""


# ------------------------------------------------------------------ HTTP
def http_get(url: str, api_key: str, retries: int = MAX_RETRIES) -> object:
    """发起 GET 并解析 JSON。

    - HTTP 429：指数退避重试（1s/2s/3s），耗尽后抛 FinnhubError。
    - 其它 HTTP 错误 / 网络错误：直接抛 FinnhubError（不重试）。
    """
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"X-Finnhub-Token": api_key})
            with URLOPEN(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
            return json.loads(raw)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                last_err = "HTTP 429 rate limited"
                if attempt < retries - 1:
                    time.sleep(attempt + 1)      # 1s, 2s, 3s（调用时查 time.sleep，可测）
                    continue
                raise FinnhubError(last_err)
            raise FinnhubError(f"HTTP {e.code} for {url}")
        except Exception as e:  # 网络超时 / 解析失败等
            raise FinnhubError(f"{type(e).__name__}: {e}")
    raise FinnhubError(last_err or "unknown error")


def _company_url(symbol: str, from_d: str, to_d: str) -> str:
    return (f"{FINNHUB_BASE}/company-news?symbol={symbol.upper()}"
            f"&from={from_d}&to={to_d}")


def _norm_item(item: object) -> dict:
    """把 Finnhub 新闻条目规范化为固定字段；缺字段以 None 兜底，绝不抛异常。"""
    if not isinstance(item, dict):
        return {}
    return {k: item.get(k) for k in NEWS_FIELDS}


def fetch_market_news(api_key: str) -> tuple[list, str | None]:
    """市场级通用新闻。返回 (列表, error_or_None)。"""
    try:
        data = http_get(MARKET_ENDPOINT, api_key)
        items = [_norm_item(x) for x in data] if isinstance(data, list) else []
        return [x for x in items if x], None
    except FinnhubError as e:
        return [], str(e)


def fetch_company_news(api_key: str, symbol: str) -> tuple[list, str | None]:
    """单只个股新闻（回溯 7 天）。返回 (列表, error_or_None)。"""
    to_d = date.today().strftime("%Y-%m-%d")
    from_d = (date.today() - timedelta(days=COMPANY_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    try:
        data = http_get(_company_url(symbol, from_d, to_d), api_key)
        items = [_norm_item(x) for x in data] if isinstance(data, list) else []
        return [x for x in items if x], None
    except FinnhubError as e:
        return [], str(e)


def collect_universe(universe_path: Path) -> list[str]:
    """从 dashboard_data.json 的股票池提取 ticker（去重、大写、去空）。失败返回 []。"""
    if not universe_path.exists():
        return []
    try:
        d = json.loads(universe_path.read_text(encoding="utf-8"))
        stocks = d.get("stocks") or []
        out = []
        for s in stocks:
            tk = (s.get("ticker") if isinstance(s, dict) else None)
            if tk:
                tk = str(tk).upper().strip()
                if tk and tk not in out:
                    out.append(tk)
        return out
    except Exception:
        return []


def read_position_tickers(path: Path) -> list[str]:
    """读 portfolio_50000_positions.csv，返回 Status=OPEN 的 ticker（大写、去重、去空）。

    文件不存在 / 解析失败 → 返回 []（不抛异常，翻译层与前端按空仓处理）。
    """
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    except Exception:
        return []
    out: list[str] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        if str(r.get("Status") or "").strip().upper() != "OPEN":
            continue
        tk = str(r.get("Ticker") or "").strip().upper()
        if tk and tk not in out:
            out.append(tk)
    return out


def _headline_hash(headline: str) -> str:
    """headline 的稳定短哈希（缓存 key）。"""
    return hashlib.sha256(str(headline).encode("utf-8")).hexdigest()[:16]


def load_translation_cache(path: Path) -> dict:
    """读翻译缓存 {hash: {headline_cn, sentiment, rationale}}；缺失/损坏 → {}。"""
    if not path.exists():
        return {}
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_translation_cache(cache: dict, path: Path) -> None:
    """写翻译缓存，失败静默（缓存是加速项，不阻断主流程）。"""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def collect_translation_targets(market_news: list, ticker_news: dict,
                                position_tickers: list[str]) -> list[dict]:
    """翻译范围：市场 top N + 每只持仓 top N（按 headline 去重）。"""
    targets: list[dict] = []
    seen: set = set()

    def add(item):
        if not isinstance(item, dict):
            return
        h = item.get("headline")
        if h and h not in seen:
            seen.add(h)
            targets.append(item)

    for item in (market_news or [])[:MARKET_TRANSLATE_TOP]:
        add(item)
    for tk in position_tickers:
        for item in (ticker_news or {}).get(tk, [])[:TICKER_TRANSLATE_TOP]:
            add(item)
    return targets


def _norm_sentiment(s) -> str:
    s = str(s or "").strip().lower()
    return s if s in _VALID_SENTIMENT else "neutral"


def _norm_rationale(s) -> str:
    """新闻情绪理由：1 句中文、≤30 字；缺失或超长（格式错）一律留空，不影响其它字段。"""
    s = str(s or "").strip()
    if not s or len(s) > 30:
        return ""
    return s


def _build_translation_prompt(headlines: list[str]) -> str:
    numbered = "\n".join(f"{i + 1}. {h}" for i, h in enumerate(headlines))
    return (
        "你是专业的金融新闻翻译与情绪标注助手。对以下每条英文新闻标题：\n"
        "1) 翻译成简洁、准确的中文（headline_cn）；\n"
        "2) 判断该新闻对该标的/市场整体是利好、利空还是中性（sentiment）；\n"
        "3) 用 rationale 字段给出『为什么是利好/利空/中性』的一句中文简评：\n"
        "   - 必须 ≤30 字，说明因果，不要重复标题；\n"
        "   - 中性也要给理由（如『信息未超出市场预期』）。\n"
        "必须严格只输出一个 JSON 数组，每项形如：\n"
        '{"headline": "<原英文标题，逐字保留>", "headline_cn": "<中文翻译>", '
        '"sentiment": "bullish|bearish|neutral", "rationale": "<一句话理由，≤30字>"}\n'
        "不要输出任何解释、Markdown 代码块或额外文字。\n\n"
        f"新闻标题列表：\n{numbered}"
    )


def _extract_json_array(text):
    """从模型输出中提取第一个完整 JSON 数组（容忍 ```json / 前后解释 / 字符串内括号）。"""
    raw = str(text or "").strip()
    if not raw:
        return None
    start = raw.find("[")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(raw)):
        ch = raw[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[start:i + 1])
                except Exception:
                    return None
    return None


def translate_headlines(headlines: list[str], client=None, model: str | None = None) -> dict:
    """批量翻译（一次 API 调用），返回 {headline: {headline_cn, sentiment, rationale}}。

    - client 未传 → 惰性复用 ClawSocketClient（claude-opus-5-5）。
    - 任何失败（缺 key / 网络 / 解析）→ 返回 {}（R1：翻译失败不阻断抓取）。
    """
    headlines = [h for h in headlines if h]
    if not headlines:
        return {}
    if client is None:
        try:
            sys.path.insert(0, str(REPO_ROOT_DEFAULT))
            from clawsocket_compat import ClawSocketClient
            client = ClawSocketClient()
        except Exception:
            return {}
    if not getattr(client, "api_key", None):
        return {}
    try:
        prompt = _build_translation_prompt(headlines)
        resp = client.messages.create(
            model=model or TRANSLATE_MODEL,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = getattr(resp, "output_text", "") or ""
        arr = _extract_json_array(text)
        if not isinstance(arr, list):
            return {}
        out: dict = {}
        for it in arr:
            if not isinstance(it, dict):
                continue
            h = it.get("headline")
            if not h:
                continue
            out[str(h)] = {
                "headline_cn": it.get("headline_cn") or None,
                "sentiment": _norm_sentiment(it.get("sentiment")),
                "rationale": _norm_rationale(it.get("rationale")),
            }
        return out
    except Exception:
        return {}


def apply_translations(items: list, cache: dict) -> list:
    """把缓存中的 headline_cn / sentiment 注入到新闻条目（就地更新）。"""
    for it in items:
        if not isinstance(it, dict):
            continue
        h = it.get("headline")
        if not h:
            continue
        tr = cache.get(_headline_hash(h))
        if isinstance(tr, dict):
            it["headline_cn"] = tr.get("headline_cn")
            it["sentiment"] = _norm_sentiment(tr.get("sentiment"))
            rat = tr.get("rationale")
            if rat:
                it["rationale"] = rat
    return items


def build_output(market_news: list, ticker_news: dict, error: str | None) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "market_news": market_news,
        "ticker_news": ticker_news,
        "error": error,
    }


def write_output(payload: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run(api_key: str, tickers: list[str], include_market: bool,
        out_path: Path = OUT_PATH_DEFAULT, position_tickers: list[str] | None = None,
        translate_fn=None, cache_path: Path | None = None) -> dict:
    """抓取主流程。返回最终 payload（也负责落盘，遵循 R1）。

    - position_tickers：当前持仓 ticker 列表（决定翻译范围 + 前端过滤）；None 时从 CSV 读。
    - translate_fn：headlines -> {headline: {headline_cn, sentiment}}；None 时用 ClawSocket 批量翻译。
    - cache_path：翻译缓存文件路径；None 时用默认路径。
    """
    market_news: list = []
    ticker_news: dict = {}
    errors: list[str] = []

    if include_market:
        items, err = fetch_market_news(api_key)
        market_news = items
        if err:
            errors.append(err)
        if tickers:
            time.sleep(SLEEP_BETWEEN)

    for sym in tickers:
        items, err = fetch_company_news(api_key, sym)
        ticker_news[sym] = items
        if err:
            errors.append(f"{sym}: {err}")
        time.sleep(SLEEP_BETWEEN)

    error = "; ".join(errors) if errors else None

    # ---- 翻译 + sentiment（R1：失败不阻断，headline_cn 留空由前端回退英文）----
    if position_tickers is None:
        position_tickers = read_position_tickers(POSITIONS_PATH_DEFAULT)
    if translate_fn is None:
        translate_fn = translate_headlines
    cache_path = cache_path or TRANSLATION_CACHE_PATH

    cache = load_translation_cache(cache_path)
    targets = collect_translation_targets(market_news, ticker_news, position_tickers)
    missing = [t["headline"] for t in targets
               if _headline_hash(t["headline"]) not in cache]
    if missing:
        try:
            translated = translate_fn(missing) or {}
        except Exception:
            translated = {}
        for h in missing:
            tr = translated.get(h)
            if isinstance(tr, dict):
                cache[_headline_hash(h)] = {
                    "headline_cn": tr.get("headline_cn"),
                    "sentiment": _norm_sentiment(tr.get("sentiment")),
                    "rationale": tr.get("rationale"),
                }
        if translated:
            save_translation_cache(cache, cache_path)
    apply_translations(market_news, cache)
    for sym in ticker_news:
        apply_translations(ticker_news[sym], cache)

    payload = build_output(market_news, ticker_news, error)

    # R1：成功抓取但零内容（无市场 + 无个股，且非错误态）→ 不落文件
    has_data = bool(market_news) or any(ticker_news.values())
    if error is None and not has_data:
        print("ℹ️ 无任何新闻数据（且无错误）→ 按 R1 原则跳过写文件")
        return payload

    write_output(payload, out_path)
    print(f"✅ 新闻数据已写入 {out_path}（市场 {len(market_news)} 条 / "
          f"个股 {sum(len(v) for v in ticker_news.values())} 条 / error={error}）")
    return payload


def main(argv=None, out_path: Path | None = None,
        universe_path: Path | None = None) -> int:
    ap = argparse.ArgumentParser(description="Finnhub 新闻抓取 → dashboard/data/news_data.json")
    ap.add_argument("--tickers", default=None,
                    help="逗号分隔的 ticker 列表；省略则从 dashboard_data.json 股票池推导")
    ap.add_argument("--no-market", action="store_true", help="跳过市场级新闻（只抓个股）")
    ap.add_argument("--out", default=None, help="输出路径（测试用，默认 dashboard/data/news_data.json）")
    ap.add_argument("--data-dir", default=None,
                    help="仓库根目录（用于推导股票池 universe，默认脚本上级目录）")
    ap.add_argument("--positions", default=None,
                    help="持仓 CSV 路径（默认 <仓库根>/portfolio_50000_positions.csv）")
    ap.add_argument("--cache", default=None,
                    help="翻译缓存路径（默认 dashboard/data/news_translation_cache.json）")
    args = ap.parse_args(argv)

    root = Path(args.data_dir) if args.data_dir else REPO_ROOT_DEFAULT
    out = Path(args.out) if args.out else (out_path or OUT_PATH_DEFAULT)
    key = os.environ.get("FINNHUB_API_KEY")

    if not key:
        # key 缺失：写空结构 + error，让前端明确展示，不崩
        print("⚠️ FINNHUB_API_KEY 未设置 → 写 error 空结构")
        write_output(build_output([], {}, "FINNHUB_API_KEY not set"), out)
        return 0

    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        upath = universe_path or (root / "dashboard" / "data" / "dashboard_data.json")
        tickers = collect_universe(upath)
        print(f"📋 从股票池推导 {len(tickers)} 只 ticker（{upath.name}）")

    positions_path = Path(args.positions) if args.positions else \
        (root / "portfolio_50000_positions.csv")
    position_tickers = read_position_tickers(positions_path)
    cache_path = Path(args.cache) if args.cache else TRANSLATION_CACHE_PATH

    run(key, tickers, include_market=not args.no_market, out_path=out,
        position_tickers=position_tickers, cache_path=cache_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
