#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""历史因子回填 · 因子层（2 年，8 扩展因子版）

从 research_price_history_2y.csv + research_spy_2y.csv 逐日重算 8 个扩展因子。
严守前视偏差：Technical_Date = T-1，Scan_Date = T。
输出 research_factor_snapshots_2y.csv。

修订记录：
  · 原实现用 ast 只抽取 calculate_extended_quant_factors 单个函数 → 其内部调用的
    momentum_pct / realized_volatility_20d_pct / volume_ratio_20d / zscore_20d /
    beta_60d / stock_rs_20d_vs_spy 不在 exec 命名空间 → 每票每天都 NameError
    → rows 恒为空 → 写出 1 字节空文件。
  · 现改为直接 import quant_factor_lab（该模块声明不 import yfinance、零网络请求），
    import 失败时回退到"exec 全部顶层函数 + 常量"的共享命名空间。
  · 异常不再静默全吞：统计 fail_count 并打印前 3 条真实异常类型。
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
PRICE_IN = REPO / "research_price_history_2y.csv"
SPY_IN = REPO / "research_spy_2y.csv"
SNAPSHOT_OUT = REPO / "research_factor_snapshots_2y.csv"


def _load_calc_extended():
    """优先 import quant_factor_lab；失败则回退 exec-all 共享命名空间。"""
    try:
        import quant_factor_lab as lab
        return lab.calculate_extended_quant_factors, "import"
    except Exception as e:
        print(f"[warn] import quant_factor_lab 失败（{type(e).__name__}: {e}），回退 exec-all")
    import ast
    src = (REPO / "quant_factor_lab.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    ns = {"pd": pd, "np": np}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.Assign)):
            try:
                exec(ast.get_source_segment(src, node), ns)
            except Exception:
                pass
    return ns["calculate_extended_quant_factors"], "exec-all"


_calc_extended, _MODE = _load_calc_extended()


def main():
    print(f"Loading price history... (loader mode: {_MODE})")
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
    fail_count = 0
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
                fail_count += 1
                if fail_count <= 3:
                    print(f"  {tk} @ {T.date()}: {type(e).__name__}: {e}")
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

    print(f"Failures: {fail_count}")
    print(f"Total rows: {len(rows)}")
    df = pd.DataFrame(rows)
    df.to_csv(SNAPSHOT_OUT, index=False, encoding="utf-8")
    print(f"Written: {SNAPSHOT_OUT}")


if __name__ == "__main__":
    main()
