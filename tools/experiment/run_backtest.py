# -*- coding: utf-8 -*-
"""独立实验 ③：用 quant_factor_backtest.run_backtest 计算每只股票的前瞻收益。

铁律：只写 /tmp/experiment/，绝不碰 /tmp/us。
run_backtest 的全部路径参数均指向 /tmp/experiment，因此不会写入仓库任何文件。
price_map 直接传入（来自 history.csv），run_backtest 不会触发任何行情下载。
"""
import os
import sys

import pandas as pd

sys.path.insert(0, "/tmp/us")  # 只读 import
from quant_factor_backtest import run_backtest

HIST = "/tmp/experiment/history.csv"
SNAP = "/tmp/experiment/snapshot.csv"
BT = "/tmp/experiment/backtest.csv"
SUM = "/tmp/experiment/summary.csv"


def _norm(series):
    idx = pd.to_datetime(series.index).tz_localize(None).normalize()
    s = pd.Series(pd.to_numeric(series.values, errors="coerce"), index=idx)
    return s.sort_index().dropna()


def main():
    if not os.path.exists(SNAP):
        print(f"缺少 {SNAP}（build_factor_snapshot.py 未生成）。实验中止。")
        sys.exit(0)

    hist = pd.read_csv(HIST, parse_dates=["Date"])
    price_map = {}
    for t, g in hist.groupby("Ticker"):
        g = g.sort_values("Date")
        s = _norm(g.set_index("Date")["Close"])
        if not s.empty:
            price_map[t] = s

    # 全部产物写入 /tmp/experiment，不碰仓库
    result = run_backtest(
        snapshot_path=SNAP,
        price_map=price_map,
        backtest_path=BT,
        summary_path=SUM,
    )
    print("[run_backtest] " + str(result))


if __name__ == "__main__":
    main()
