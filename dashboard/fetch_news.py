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
import json
import os
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
        out_path: Path = OUT_PATH_DEFAULT) -> dict:
    """抓取主流程。返回最终 payload（也负责落盘，遵循 R1）。"""
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
    args = ap.parse_args(argv)

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
        root = Path(args.data_dir) if args.data_dir else REPO_ROOT_DEFAULT
        upath = universe_path or (root / "dashboard" / "data" / "dashboard_data.json")
        tickers = collect_universe(upath)
        print(f"📋 从股票池推导 {len(tickers)} 只 ticker（{upath.name}）")

    run(key, tickers, include_market=not args.no_market, out_path=out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
