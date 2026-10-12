# -*- coding: utf-8 -*-
"""独立实验 ③（CI 版）：用 quant_factor_backtest.run_backtest 计算每只股票的前瞻收益。

CI 调整：sys.path 指向仓库根目录做只读 import；I/O 写入脚本同目录（_temp_experiment/）。
price_map 直接传入（来自 history.csv），run_backtest 不会触发任何行情下载。
"""
import os
import sys

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)  # 只读 import 仓库根目录的 quant_factor_backtest
from quant_factor_backtest import run_backtest

HIST = os.path.join(_HERE, "history.csv")
SNAP = os.path.join(_HERE, "snapshot.csv")
BT = os.path.join(_HERE, "backtest.csv")
SUM = os.path.join(_HERE, "summary.csv")


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

    # 全部产物写入脚本同目录，不碰仓库
    result = run_backtest(
        snapshot_path=SNAP,
        price_map=price_map,
        backtest_path=BT,
        summary_path=SUM,
    )
    print("[run_backtest] " + str(result))


if __name__ == "__main__":
    main()
