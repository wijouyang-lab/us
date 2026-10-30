#!/usr/bin/env python3
"""Unified historical technical-factor engine.

Inputs are raw split-adjusted OHLCV (no dividend adjustment) plus an optional
SPY series. Factors use only data at or before each date. Forward returns are
NOT computed here; use tools.research.forward_return.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

FACTORS = [
    "MA20", "MA50", "MA200", "MA20_Slope_5D", "MACD_Hist", "ADX14",
    "Momentum_5D", "Momentum_20D", "Momentum_60D", "Momentum_120D",
    "RSI14", "KDJ_J", "Bias20", "ATR_Percent", "Realized_Volatility_20D",
    "Beta_60D", "ZScore20", "Volume_Ratio_5D", "Volume_Ratio_20D",
    "Stock_RS_20D_vs_SPY",
]
WARMUP = {
    "MA20": 20, "MA50": 50, "MA200": 200, "MA20_Slope_5D": 25,
    "MACD_Hist": 35, "ADX14": 28,
    "Momentum_5D": 5, "Momentum_20D": 20, "Momentum_60D": 60, "Momentum_120D": 120,
    "RSI14": 14, "KDJ_J": 9, "Bias20": 20, "ATR_Percent": 14,
    "Realized_Volatility_20D": 20, "Beta_60D": 60, "ZScore20": 20,
    "Volume_Ratio_5D": 5, "Volume_Ratio_20D": 20, "Stock_RS_20D_vs_SPY": 20,
}


def factor_status(value, bars_seen: int, warmup: int, input_present: bool = True) -> str:
    if not input_present:
        return "MISSING_INPUT"
    if bars_seen < warmup:
        return "FACTOR_WARMUP"
    if pd.isna(value):
        return "MISSING_INPUT"
    return "FACTOR_AVAILABLE"


def _wilder(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def _calc_group(g: pd.DataFrame, spy: pd.DataFrame | None) -> pd.DataFrame:
    g = g.sort_values("Date").reset_index(drop=True).copy()
    c, h, l, v = g["Close"], g["High"], g["Low"], g["Volume"]
    ret = c.pct_change()
    g["MA20"] = c.rolling(20, min_periods=20).mean()
    g["MA50"] = c.rolling(50, min_periods=50).mean()
    g["MA200"] = c.rolling(200, min_periods=200).mean()
    g["MA20_Slope_5D"] = g["MA20"] / g["MA20"].shift(5) - 1
    ema12 = c.ewm(span=12, adjust=False, min_periods=12).mean()
    ema26 = c.ewm(span=26, adjust=False, min_periods=26).mean()
    macd = ema12 - ema26
    g["MACD_Hist"] = macd - macd.ewm(span=9, adjust=False, min_periods=9).mean()
    prev = c.shift(1)
    tr = pd.concat([(h - l).abs(), (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    atr = _wilder(tr, 14)
    up = h.diff()
    dn = -l.diff()
    plus_dm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=g.index)
    minus_dm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=g.index)
    plus_di = 100 * _wilder(plus_dm, 14) / atr
    minus_di = 100 * _wilder(minus_dm, 14) / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    g["ADX14"] = _wilder(dx, 14)
    g["Momentum_5D"] = c / c.shift(5) - 1
    g["Momentum_20D"] = c / c.shift(20) - 1
    g["Momentum_60D"] = c / c.shift(60) - 1
    g["Momentum_120D"] = c / c.shift(120) - 1
    delta = c.diff()
    gain = _wilder(delta.clip(lower=0), 14)
    loss = _wilder(-delta.clip(upper=0), 14)
    g["RSI14"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    low9 = l.rolling(9, min_periods=9).min()
    high9 = h.rolling(9, min_periods=9).max()
    rsv = (c - low9) / (high9 - low9).replace(0, np.nan)
    k = rsv.ewm(alpha=1 / 3, adjust=False, min_periods=9).mean()
    d = k.ewm(alpha=1 / 3, adjust=False, min_periods=9).mean()
    g["KDJ_J"] = 3 * k - 2 * d
    g["Bias20"] = c / g["MA20"] - 1
    g["ATR_Percent"] = atr / c
    g["Realized_Volatility_20D"] = ret.rolling(20, min_periods=20).std() * np.sqrt(252)
    std20 = c.rolling(20, min_periods=20).std()
    g["ZScore20"] = (c - g["MA20"]) / std20.replace(0, np.nan)
    vma5 = v.rolling(5, min_periods=5).mean()
    vma20 = v.rolling(20, min_periods=20).mean()
    g["Volume_Ratio_5D"] = v / vma5.replace(0, np.nan)
    g["Volume_Ratio_20D"] = v / vma20.replace(0, np.nan)
    if spy is not None and not spy.empty:
        s = spy[["Date", "Close"]].rename(columns={"Close": "SPY_Close"}).sort_values("Date")
        s["SPY_Ret20"] = s["SPY_Close"] / s["SPY_Close"].shift(20) - 1
        s["SPY_Ret1"] = s["SPY_Close"].pct_change()
        m = g[["Date"]].merge(s, on="Date", how="left")
        g["Stock_RS_20D_vs_SPY"] = (c / c.shift(20) - 1).to_numpy() - m["SPY_Ret20"].to_numpy()
        stock_ret = ret.reset_index(drop=True)
        spy_ret = m["SPY_Ret1"].reset_index(drop=True)
        cov = stock_ret.rolling(60, min_periods=60).cov(spy_ret)
        var = spy_ret.rolling(60, min_periods=60).var()
        g["Beta_60D"] = cov / var.replace(0, np.nan)
    else:
        g["Stock_RS_20D_vs_SPY"] = np.nan
        g["Beta_60D"] = np.nan
    return g


def compute_factors(price: pd.DataFrame, spy: pd.DataFrame | None = None) -> pd.DataFrame:
    if spy is not None:
        spy = spy.copy()
        spy["Date"] = pd.to_datetime(spy["Date"], errors="coerce")
    d = price.copy()
    d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
    d["Ticker"] = d["Ticker"].astype(str).str.upper().str.strip()
    for col in ("Open", "High", "Low", "Close", "Volume"):
        d[col] = pd.to_numeric(d[col], errors="coerce")
    d = d.dropna(subset=["Date", "Ticker"]).sort_values(["Ticker", "Date"])
    out = []
    for ticker, g in d.groupby("Ticker", sort=True):
        try:
            out.append(_calc_group(g, spy))
        except Exception:
            # Keep the ticker's raw rows with missing factors rather than aborting.
            bad = g.copy()
            for f in FACTORS:
                bad[f] = np.nan
            out.append(bad)
    result = pd.concat(out, ignore_index=True) if out else pd.DataFrame()
    ordered = ["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"] + FACTORS
    return result[ordered].sort_values(["Ticker", "Date"]).reset_index(drop=True)


def coverage_summary(factors: pd.DataFrame) -> dict:
    total = len(factors)
    by_ticker = factors.groupby("Ticker").size()
    out = {"rows": total, "tickers": int(factors.Ticker.nunique()),
           "date_min": str(factors.Date.min().date()), "date_max": str(factors.Date.max().date()),
           "factors": {}}
    bars = factors.groupby("Ticker").cumcount() + 1
    for f in FACTORS:
        valid = int(factors[f].notna().sum())
        out["factors"][f] = {"valid": valid, "missing": total - valid,
                             "coverage": valid / total if total else 0.0,
                             "warmup": int((bars < WARMUP[f]).sum())}
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--price-panel", required=True)
    p.add_argument("--spy", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--summary", required=True)
    args = p.parse_args(argv)
    price = pd.read_csv(args.price_panel, usecols=["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"])
    spy = pd.read_csv(args.spy, usecols=["Date", "Close"])
    factors = compute_factors(price, spy)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    factors.to_parquet(args.output, index=False)
    summary = coverage_summary(factors)
    summary["output"] = args.output
    Path(args.summary).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
