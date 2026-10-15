#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""历史因子回填 · 因子层（2 年，8 扩展因子版）

从 research_price_history_2y.csv + research_spy_2y.csv 逐日重算 8 个扩展因子。
严守前视偏差：Technical_Date = T-1，Scan_Date = T。
输出 research_factor_snapshots_2y.csv。
"""
import ast
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
PRICE_IN = REPO / "research_price_history_2y.csv"
SPY_IN = REPO / "research_spy_2y.csv"
SNAPSHOT_OUT = REPO / "research_factor_snapshots_2y.csv"
LAB_PY = REPO / "quant_factor_lab.py"


def _extract_func(name):
    src = LAB_PY.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            ns = {"pd": pd, "np": np}
            exec(ast.get_source_segment(src, node), ns)
            return ns[name]
    raise AssertionError(f"{name} not found in {LAB_PY}")


_calc_extended = _extract_func("calculate_extended_quant_factors")


def main():
    print("Loading price history...")
    stocks = pd.read_csv(PRICE_IN, dtype={"Date": str, "Ticker": str})
    spy = pd.read_csv(SPY_IN, dtype={"Date": str})
    stocks["Date"] = pd.to_datetime(stocks["Date"])
    spy["Date"] = pd.to_datetime(spy["Date"])
    stocks = stocks.sort_values(["Ticker", "Date"]).reset_index(drop=True)
    spy = spy.sort_values("Date").reset_index(drop=True)

    all_dates = sorted(spy["Date"].unique())
    print(f"Trading days: {len(all_dates)}")

    by_ticker = {t: g.reset_index(drop=True) for t, g in stocks.groupby("Ticker")}
    print(f"Tickers: {len(by_ticker)}")

    rows = []
    # 从第 60 个交易日开始（60D Beta 需要 60 根 bar）
    for i, T in enumerate(all_dates[60:], start=60):
        T_prev = all_dates[i - 1]
        spy_win = spy[spy["Date"] <= T_prev]
        if len(spy_win) < 60:
            continue
        spy_close = spy_win.set_index("Date")["Close"]
        for tk, g in by_ticker.items():
            win = g[g["Date"] <= T_prev]
            if len(win) < 60:
                continue
            win2 = win.set_index("Date")
            try:
                factors = _calc_extended(win2, spy_close)
            except Exception as e:
                print(f"  {tk} @ {T.date()}: {e}")
                continue
            row = {
                "Scan_Date": T.strftime("%Y-%m-%d"),
                "Technical_Date": T_prev.strftime("%Y-%m-%d"),
                "Ticker": tk,
                "Price": float(win2["Close"].iloc[-1]),
                "schema_version": "phase1.v1",
            }
            for k, v in factors.items():
                row[k] = "" if v is None else round(float(v), 6)
            rows.append(row)

    print(f"Total rows: {len(rows)}")
    df = pd.DataFrame(rows)
    df.to_csv(SNAPSHOT_OUT, index=False, encoding="utf-8")
    print(f"Written: {SNAPSHOT_OUT}")


if __name__ == "__main__":
    main()
