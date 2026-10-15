#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S&P 500 复验 · 数据层（10 年）

从 Wikipedia 抓 S&P 500 当前成分（503 只）+ 追加 SPY，
用 yfinance 拉 10 年日线，写入独立文件（不碰 2 年版产物）。

输出：
  research_price_history_sp500_10y.csv
  research_spy_sp500_10y.csv

schema_version 保持 "phase2b.v1"。
与 2 年版唯一差异 = YEARS（2→10）+ 2 个输出文件名。
"""
import sys
import time
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

REPO = Path(__file__).resolve().parent.parent.parent
PRICE_OUT = REPO / "research_price_history_sp500_10y.csv"
SPY_OUT = REPO / "research_spy_sp500_10y.csv"
BATCH = 20
SLEEP_SEC = 3.0
YEARS = 10
WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def load_tickers():
    """从 Wikipedia 抓 S&P 500 当前成分，去重排序，追加 SPY。"""
    resp = requests.get(WIKI_URL, headers={"User-Agent": UA}, timeout=30)
    resp.raise_for_status()
    tables = pd.read_html(StringIO(resp.text))
    df = tables[0]
    tickers = set()
    for sym in df["Symbol"].tolist():
        s = str(sym).strip().upper().replace(".", "-")  # BRK.B -> BRK-B
        if s:
            tickers.add(s)
    tickers.add("SPY")
    print(f"[backfill-sp500-10y] loaded {len(tickers)-1} tickers from Wikipedia + SPY")
    return sorted(tickers)


def fetch_batch(tickers, start, end):
    """批量下载一批 ticker 的 OHLCV。"""
    import yfinance as yf
    rows = []
    try:
        data = yf.download(
            tickers, start=start, end=end,
            progress=False, auto_adjust=False, threads=True, group_by="ticker",
        )
    except Exception as e:
        print(f"[fetch_batch] yf.download failed: {e}", file=sys.stderr)
        return rows
    if data is None or data.empty:
        return rows
    for tk in tickers:
        try:
            sub = data[tk] if len(tickers) > 1 else data
            if sub is None or sub.empty:
                continue
            for idx, r in sub.iterrows():
                close = r.get("Close")
                if pd.isna(close):
                    continue

                def _v(x):
                    return "" if pd.isna(x) else round(float(x), 6)

                vol = r.get("Volume")
                rows.append({
                    "Date": pd.Timestamp(idx).strftime("%Y-%m-%d"),
                    "Ticker": tk,
                    "Open": _v(r.get("Open")),
                    "High": _v(r.get("High")),
                    "Low": _v(r.get("Low")),
                    "Close": round(float(close), 6),
                    "Volume": "" if pd.isna(vol) else int(vol),
                    "schema_version": "phase2b.v1",
                })
        except Exception as e:
            print(f"[fetch_batch] {tk}: {e}", file=sys.stderr)
    return rows


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=365 * YEARS + 30)).strftime("%Y-%m-%d")
    tickers = load_tickers()
    print(f"[backfill-sp500-10y] targets: {len(tickers)} tickers, {start} ~ {today}")

    all_rows = []
    for i in range(0, len(tickers), BATCH):
        batch = tickers[i:i + BATCH]
        print(f"[batch {i // BATCH + 1}] {len(batch)} tickers")
        all_rows.extend(fetch_batch(batch, start, today))
        time.sleep(SLEEP_SEC)

    if not all_rows:
        print("[backfill-sp500-10y] no rows fetched, abort")
        return 1

    df = pd.DataFrame(all_rows)
    df = df.sort_values(["Date", "Ticker"]).reset_index(drop=True)

    spy = df[df["Ticker"] == "SPY"].copy()
    stocks = df[df["Ticker"] != "SPY"].copy()

    stocks.to_csv(PRICE_OUT, index=False, encoding="utf-8")
    spy.to_csv(SPY_OUT, index=False, encoding="utf-8")
    print(f"[backfill-sp500-10y] written {PRICE_OUT.name}: {len(stocks)} rows")
    print(f"[backfill-sp500-10y] written {SPY_OUT.name}: {len(spy)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
