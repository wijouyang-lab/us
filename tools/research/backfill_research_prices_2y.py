#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""历史因子回填 · 数据层（2 年）

从 trade_history.csv 提取全部 ticker + 追加 SPY，用 yfinance 拉 2 年日线，
写入独立文件（不碰生产 quant_factor_price_history.csv）。

输出：
  research_price_history_2y.csv  — Date,Ticker,Open,High,Low,Close,Volume,schema_version
  research_spy_2y.csv            — 同上，仅 SPY

schema_version 保持 "phase2b.v1"（供研究侧校验）。
"""
import csv
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
TRADE_HISTORY = REPO / "trade_history.csv"
PRICE_OUT = REPO / "research_price_history_2y.csv"
SPY_OUT = REPO / "research_spy_2y.csv"
BATCH = 20
SLEEP_SEC = 3.0
YEARS = 2


def load_tickers():
    """从 trade_history.csv 提取全部 ticker，去重排序，追加 SPY。"""
    tickers = set()
    if TRADE_HISTORY.exists():
        with open(TRADE_HISTORY, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                t = (row.get("Ticker") or "").strip().upper()
                if t:
                    tickers.add(t)
    tickers.add("SPY")
    return sorted(tickers)


def fetch_batch(tickers, start, end):
    """批量下载一批 ticker 的 OHLCV，返回 list of dict。"""
    import yfinance as yf
    import pandas as pd
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
    import pandas as pd
    today = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=365 * YEARS + 30)).strftime("%Y-%m-%d")
    tickers = load_tickers()
    print(f"[backfill-2y] targets: {len(tickers)} tickers, {start} ~ {today}")

    all_rows = []
    for i in range(0, len(tickers), BATCH):
        batch = tickers[i:i + BATCH]
        print(f"[batch {i // BATCH + 1}] {len(batch)} tickers")
        all_rows.extend(fetch_batch(batch, start, today))
        time.sleep(SLEEP_SEC)

    if not all_rows:
        print("[backfill-2y] no rows fetched, abort")
        return 1

    df = pd.DataFrame(all_rows)
    df = df.sort_values(["Date", "Ticker"]).reset_index(drop=True)

    # 分离 SPY
    spy = df[df["Ticker"] == "SPY"].copy()
    stocks = df[df["Ticker"] != "SPY"].copy()

    stocks.to_csv(PRICE_OUT, index=False, encoding="utf-8")
    spy.to_csv(SPY_OUT, index=False, encoding="utf-8")
    print(f"[backfill-2y] written {PRICE_OUT.name}: {len(stocks)} rows")
    print(f"[backfill-2y] written {SPY_OUT.name}: {len(spy)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
