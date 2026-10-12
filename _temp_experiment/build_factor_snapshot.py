# -*- coding: utf-8 -*-
"""独立实验 ②（CI 版）：对每天/每只股票用 quant_factor_lab.calculate_extended_quant_factors 算技术因子。

CI 调整：sys.path 指向仓库根目录（_temp_experiment 的父目录）做只读 import；
I/O 写入脚本同目录（_temp_experiment/）。不重新实现因子逻辑，不碰仓库现有文件。
输出结构对齐 SNAPSHOT_COLUMNS，便于 run_backtest 直接消费。
"""
import os
import sys

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)  # 只读 import 仓库根目录的 quant_factor_lab
from quant_factor_lab import calculate_extended_quant_factors, SNAPSHOT_COLUMNS, SCHEMA_VERSION

HIST = os.path.join(_HERE, "history.csv")
OUT = os.path.join(_HERE, "snapshot.csv")
STOCKS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO",
    "JPM", "V", "UNH", "XOM", "JNJ", "WMT", "MA", "PG", "HD", "CVX",
    "LLY", "KO",
]
WARMUP = 60  # 因子窗口最大 60D，留足预热


def _norm(series):
    idx = pd.to_datetime(series.index).tz_localize(None).normalize()
    s = pd.Series(pd.to_numeric(series.values, errors="coerce"), index=idx)
    return s.sort_index().dropna()


def main():
    if not os.path.exists(HIST):
        print(f"缺少 {HIST}（fetch_history.py 可能受限于沙箱限流）。实验中止。")
        sys.exit(0)

    hist = pd.read_csv(HIST, parse_dates=["Date"])
    prices, vols = {}, {}
    for t, g in hist.groupby("Ticker"):
        g = g.sort_values("Date")
        prices[t] = _norm(g.set_index("Date")["Close"])
        vols[t] = _norm(g.set_index("Date")["Volume"])
    spy = prices.get("SPY")

    rows = []
    for t in STOCKS:
        if t not in prices:
            print(f"  跳过（无数据）: {t}")
            continue
        close, volume = prices[t], vols[t]
        n = len(close)
        if n < WARMUP + 20:
            print(f"  跳过（数据不足）: {t}")
            continue
        for i in range(WARMUP, n - 20):  # 保证 T+20 交易日存在
            win_close = close.iloc[:i + 1]
            win_vol = volume.iloc[:i + 1]
            wdf = pd.DataFrame({"Close": win_close, "Volume": win_vol})
            spy_win = spy.iloc[:i + 1] if spy is not None else None
            fac = calculate_extended_quant_factors(wdf, spy_close=spy_win)
            tdate = close.index[i]
            row = {c: "" for c in SNAPSHOT_COLUMNS}
            row["Scan_Date"] = str(tdate.date())
            row["Technical_Date"] = str(tdate.date())
            row["Ticker"] = t
            row["Price"] = round(float(close.iloc[i]), 4)
            for k, v in fac.items():
                row[k] = "" if v is None else v
            row["schema_version"] = SCHEMA_VERSION
            rows.append(row)

    if not rows:
        print("未生成任何 snapshot 行（可能历史数据缺失）。")
        sys.exit(0)

    snap = pd.DataFrame(rows, columns=SNAPSHOT_COLUMNS)
    snap.to_csv(OUT, index=False)
    print(f"snapshot 行数={len(snap)}，覆盖股票={snap['Ticker'].nunique()}，"
          f"日期跨度 {snap['Technical_Date'].min()} ~ {snap['Technical_Date'].max()}")


if __name__ == "__main__":
    main()
