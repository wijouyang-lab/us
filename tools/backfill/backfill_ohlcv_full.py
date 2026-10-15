#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性回填 OHLCV：从 trade_history.csv 提取 ticker + 日期范围，
用 yfinance 批量下载，upsert 到 quant_factor_price_history.csv。

设计：
- 目标 ticker = trade_history.csv 中出现过的所有 ticker
- 日期范围 = 最早入场日 - 5 天 ~ 最晚退出日 + 1 天
- 批量下载（20 ticker/批，批间 sleep 3s）
- upsert：按 (Date, Ticker) 去重，phase2b.v2 优先，避免覆盖已完成行
- 仅补 OHLCV，绝不覆盖非空 Close
"""
import csv
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
TRADE_HISTORY = REPO / "trade_history.csv"
PRICE_HISTORY = REPO / "quant_factor_price_history.csv"
BATCH = 20
SLEEP_SEC = 3.0


def load_targets():
    """从 trade_history.csv 提取 (tickers, min_date, max_date)。"""
    tickers = set()
    min_d = None
    max_d = None
    with open(TRADE_HISTORY, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            t = (row.get("Ticker") or "").strip().upper()
            if t:
                tickers.add(t)
            for key in ("Date", "Exit_Date"):
                d = (row.get(key) or "")[:10]
                if len(d) == 10 and d[4] == "-":
                    if min_d is None or d < min_d:
                        min_d = d
                    if max_d is None or d > max_d:
                        max_d = d
    if min_d:
        dt = datetime.strptime(min_d, "%Y-%m-%d") - timedelta(days=5)
        min_d = dt.strftime("%Y-%m-%d")
    if max_d:
        dt = datetime.strptime(max_d, "%Y-%m-%d") + timedelta(days=1)
        max_d = dt.strftime("%Y-%m-%d")
    return sorted(tickers), min_d, max_d


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
                    "schema_version": "phase2b.v2",
                })
        except Exception as e:
            print(f"[fetch_batch] {tk}: {e}", file=sys.stderr)
    return rows


def main():
    import pandas as pd
    tickers, min_d, max_d = load_targets()
    print(f"[backfill] targets: {len(tickers)} tickers, {min_d} ~ {max_d}")
    if not tickers or not min_d or not max_d:
        print("[backfill] no targets, abort")
        return 1

    if not PRICE_HISTORY.exists():
        print(f"[backfill] {PRICE_HISTORY} not found, abort")
        return 1
    existing = pd.read_csv(PRICE_HISTORY, dtype=str, keep_default_na=False)
    if "schema_version" not in existing.columns:
        existing["schema_version"] = "phase2b.v1"
    print(f"[backfill] existing rows: {len(existing)}")

    all_new = []
    for i in range(0, len(tickers), BATCH):
        batch = tickers[i:i + BATCH]
        print(f"[batch {i // BATCH + 1}] {len(batch)} tickers")
        all_new.extend(fetch_batch(batch, min_d, max_d))
        time.sleep(SLEEP_SEC)

    if not all_new:
        print("[backfill] no rows fetched, abort")
        return 1
    new_df = pd.DataFrame(all_new)
    print(f"[backfill] fetched rows: {len(new_df)}")

    combined = pd.concat([existing, new_df], ignore_index=True)
    combined = combined.sort_values(
        ["Date", "Ticker", "schema_version"],
        ascending=[True, True, False],
    )
    combined = combined.drop_duplicates(subset=["Date", "Ticker"], keep="first")
    combined = combined.sort_values(["Date", "Ticker"]).reset_index(drop=True)
    combined.to_csv(PRICE_HISTORY, index=False, encoding="utf-8")
    print(f"[backfill] merged rows: {len(combined)} (delta: {len(combined) - len(existing):+d})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
