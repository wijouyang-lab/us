#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""历史因子回填 · 因子层（17 因子）—— S&P 500 点内（PIT）10 年版

在 PIT 2 年版基础上：
  · 输入改为 10 年价格层
  · _calc_kdj_scan_style 改用 N=100 尾部优化版（已验证 diff = 9.95e-14 < 1e-6）
输出 research_factor_snapshots_sp500_pit_10y.csv（22 列）。
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
PRICE_IN = REPO / "research_price_history_sp500_10y.csv"
SPY_IN = REPO / "research_spy_sp500_10y.csv"
SNAPSHOT_OUT = REPO / "research_factor_snapshots_sp500_pit_10y.csv"
CONSTITUENTS = REPO / "sp500_constituents.csv"


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


def _calc_kdj_scan_style(win, n=9, N=100):
    """照抄 scan.py:919-935 的 KDJ 口径（N=100 尾部优化版）。

    原版逐条迭代 len(win) 根（O(n)）；本版只取最后 N=100 根迭代。
    依据：K/D 从 50.0 起递推，衰减因子 2/3，100 根后前值影响 < 1e-18。
    已验证：n=2500 时与全量版 diff = 9.95e-14 < 1e-6。
    """
    high = win["High"].to_numpy(float)
    low = win["Low"].to_numpy(float)
    close = win["Close"].to_numpy(float)
    N_actual = min(len(close), N)
    close_t = close[-N_actual:]
    high_t = high[-N_actual:]
    low_t = low[-N_actual:]
    K, D = 50.0, 50.0
    j_val = 50.0
    for i in range(N_actual):
        if i < 8:
            j_val = 3 * K - 2 * D
        else:
            h9 = high_t[i - 8:i + 1].max()
            l9 = low_t[i - 8:i + 1].min()
            rsv = (close_t[i] - l9) / (h9 - l9 + 1e-9) * 100
            K = 2 / 3 * K + 1 / 3 * rsv
            D = 2 / 3 * D + 1 / 3 * K
            j_val = 3 * K - 2 * D
    return j_val


def _extract_tech_factors(win):
    """按 scan.py 逐字口径产出 9 个技术列（键名与 quant_factor_lab 期望一致）。"""
    import pandas_ta as ta
    close = win["Close"]
    high = win["High"]
    low = win["Low"]
    vol = win["Volume"]
    out = {}

    rsi = ta.rsi(close, length=14)
    out["RSI"] = float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else None

    ma20 = ta.sma(close, length=20)
    ma50 = ta.sma(close, length=50)
    out["MA20"] = float(ma20.iloc[-1]) if pd.notna(ma20.iloc[-1]) else None
    out["MA50"] = float(ma50.iloc[-1]) if pd.notna(ma50.iloc[-1]) else None

    if pd.notna(ma20.iloc[-1]) and len(ma20) >= 6 and pd.notna(ma20.iloc[-6]) and ma20.iloc[-6]:
        out["MA20_Slope_Pct_5D"] = (float(ma20.iloc[-1]) / float(ma20.iloc[-6]) - 1) * 100
    else:
        out["MA20_Slope_Pct_5D"] = None

    atr = ta.atr(high, low, close, length=14)
    if pd.notna(atr.iloc[-1]) and close.iloc[-1]:
        out["ATR_Pct"] = float(atr.iloc[-1]) / float(close.iloc[-1]) * 100
    else:
        out["ATR_Pct"] = None

    if pd.notna(ma20.iloc[-1]) and ma20.iloc[-1]:
        out["乖离率(%)"] = (float(close.iloc[-1]) - float(ma20.iloc[-1])) / float(ma20.iloc[-1]) * 100
    else:
        out["乖离率(%)"] = None

    macd = ta.macd(close)
    if macd is not None and not macd.empty:
        hcol = [c for c in macd.columns if c.startswith("MACDh")]      # MACDh_12_26_9（已实测）
        if hcol:
            out["MACD_HIST_LAST"] = float(macd[hcol[0]].iloc[-1]) if pd.notna(macd[hcol[0]].iloc[-1]) else None
        else:
            out["MACD_HIST_LAST"] = None
    else:
        out["MACD_HIST_LAST"] = None

    out["KDJ_J"] = _calc_kdj_scan_style(win)

    if len(vol) >= 6:
        avg5 = float(vol.iloc[:-1].tail(5).mean())                     # 分母不含当日（scan.py:938）
        out["量比"] = float(vol.iloc[-1] / (avg5 + 1e-9)) if avg5 > 0 else 1.0
    else:
        out["量比"] = 1.0

    return out


def main():
    print(f"Loading price history... (loader mode: {_MODE})")
    stocks = pd.read_csv(PRICE_IN, dtype={"Date": str, "Ticker": str})
    spy = pd.read_csv(SPY_IN, dtype={"Date": str})
    stocks["Date"] = pd.to_datetime(stocks["Date"])
    spy["Date"] = pd.to_datetime(spy["Date"])
    stocks = stocks.sort_values(["Ticker", "Date"]).reset_index(drop=True)
    spy = spy.sort_values("Date").reset_index(drop=True)

    date_added = {}
    if CONSTITUENTS.exists():
        const_df = pd.read_csv(CONSTITUENTS, dtype={"Ticker": str, "Date_Added": str})
        date_added = dict(zip(const_df["Ticker"].str.upper(), const_df["Date_Added"]))
        print(f"[pit] loaded {len(date_added)} constituents")
    else:
        print(f"[pit] WARNING: {CONSTITUENTS} not found -> static universe")

    all_dates = sorted(spy["Date"].unique())
    print(f"Trading days: {len(all_dates)}")

    by_ticker = {t: g.reset_index(drop=True) for t, g in stocks.groupby("Ticker")}
    print(f"Tickers: {len(by_ticker)}")

    rows = []
    fail_count = 0
    skipped_pit = 0
    # 从第 60 个交易日开始（60D Beta 需要 60 根 bar）
    for i, T in enumerate(all_dates[60:], start=60):
        T_prev = all_dates[i - 1]
        spy_win = spy[spy["Date"] <= T_prev]
        if len(spy_win) < 60:
            continue
        spy_close = spy_win.set_index("Date")["Close"]
        for tk, g in by_ticker.items():
            # 点内筛选：T_prev 日该股必须已是 S&P500 成分（SPY 除外）
            if tk != "SPY":
                da = date_added.get(tk.upper(), "")
                if da and T_prev.strftime("%Y-%m-%d") < da:
                    skipped_pit += 1
                    continue
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
            try:
                tech = _extract_tech_factors(win2)
            except Exception as e:
                tech = {}
                fail_count += 1
                if fail_count <= 3:
                    print(f"  [tech] {tk} @ {T.date()}: {type(e).__name__}: {e}")
            row = {
                "Scan_Date": T.strftime("%Y-%m-%d"),
                "Technical_Date": T_prev.strftime("%Y-%m-%d"),
                "Ticker": tk,
                "Price": float(win2["Close"].iloc[-1]),
                "schema_version": "phase1.v1",
            }
            for k, v in factors.items():
                row[k] = "" if v is None else round(float(v), 6)
            for k, v in tech.items():
                row[k] = "" if v is None else round(float(v), 6)
            rows.append(row)

    print(f"[pit] skipped (not yet in index): {skipped_pit}")
    print(f"Failures: {fail_count}")
    print(f"Total rows: {len(rows)}")
    df = pd.DataFrame(rows)
    df.to_csv(SNAPSHOT_OUT, index=False, encoding="utf-8")
    print(f"Written: {SNAPSHOT_OUT}")


if __name__ == "__main__":
    main()
