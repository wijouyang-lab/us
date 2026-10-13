# -*- coding: utf-8 -*-
"""独立实验 ①：用 yfinance 拉取 20 只 SP500 代表股 + SPY 的 10 年日线。

铁律：只写 /tmp/experiment/，绝不碰 /tmp/us。
限流降级：批次拉取 + 失败重试 3 次；若全部失败 → 报告沙箱限流并退出（不硬撑）。
"""
import os
import sys
import time

import pandas as pd

try:
    import yfinance as yf
except ImportError:
    print("yfinance 未安装，请先 pip install yfinance")
    sys.exit(2)

# 20 只 SP500 代表股（覆盖科技/金融/医疗/能源/消费/工业）
TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO",
    "JPM", "V", "UNH", "XOM", "JNJ", "WMT", "MA", "PG", "HD", "CVX",
    "LLY", "KO",
]
BENCH = "SPY"  # Beta / RS 需要的基准
ALL = TICKERS + [BENCH]

START = "2016-01-01"
END = "2026-10-12"
OUT = "/tmp/experiment/history.csv"
BATCH = 5
RETRY = 3
SLEEP = 2


def fetch_batch(batch):
    for attempt in range(1, RETRY + 1):
        try:
            df = yf.download(
                batch, start=START, end=END, progress=False,
                auto_adjust=True, group_by="ticker", threads=False,
            )
            if df is None or (hasattr(df, "empty") and df.empty):
                print(f"  [retry {attempt}] 空结果")
                time.sleep(SLEEP)
                continue
            return df
        except Exception as e:  # noqa: BLE001
            print(f"  [retry {attempt}] {type(e).__name__}: {e}")
            time.sleep(SLEEP)
    return None


def main():
    os.makedirs("/tmp/experiment", exist_ok=True)
    rows = []
    failed = []
    for i in range(0, len(ALL), BATCH):
        batch = ALL[i:i + BATCH]
        print(f"fetching {batch} ...")
        df = fetch_batch(batch)
        if df is None:
            failed.extend(batch)
            time.sleep(SLEEP)
            continue
        multi = len(batch) > 1
        for t in batch:
            try:
                sub = (df[t] if multi else df).copy()
                if sub is None or (hasattr(sub, "empty") and sub.empty):
                    failed.append(t)
                    continue
                sub = sub.reset_index()
                date_col = sub.columns[0]
                sub = sub.rename(columns={date_col: "Date"})
                sub["Ticker"] = t
                rows.append(sub[["Date", "Ticker", "Open", "High", "Low",
                                 "Close", "Adj Close", "Volume"]])
            except Exception as e:  # noqa: BLE001
                print(f"  parse {t} failed: {e}")
                failed.append(t)
        time.sleep(SLEEP)

    if not rows:
        print("沙箱限流：yfinance 全部请求失败，无法获取历史数据。"
              "实验中止（不硬撑，不伪造数据）。")
        sys.exit(0)

    hist = pd.concat(rows, ignore_index=True)
    hist.to_csv(OUT, index=False)
    print(f"保存 {len(hist)} 行到 {OUT}；失败/缺失: {failed}")


if __name__ == "__main__":
    main()
