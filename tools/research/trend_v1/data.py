"""Price loading, feature computation and ETF/stock coverage audit."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REQUIRED = ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"]


def _read_one(path: Path, ticker: str | None = None, asset_class: str = "STOCK") -> pd.DataFrame:
    d = pd.read_csv(path, low_memory=False)
    if ticker and "Ticker" not in d:
        d["Ticker"] = ticker
    for c in ("Date", "Ticker", "Open", "High", "Low", "Close", "Volume"):
        if c not in d:
            raise ValueError(f"{path}: missing column {c}")
    d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
    d["Ticker"] = d["Ticker"].astype(str).str.upper().str.strip()
    for c in ("Open", "High", "Low", "Close", "Volume"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["asset_class"] = asset_class
    return d.dropna(subset=["Date", "Ticker"])


def load_panel(stock_path: Path, etf_dir: Path, benchmark_ticker: str = "SPY") -> pd.DataFrame:
    """Combine stock panel and one-CSV-per-ticker ETFs; benchmark remains separate."""
    frames = [_read_one(Path(stock_path))]
    for p in sorted(Path(etf_dir).glob("*.csv")):
        t = p.stem.upper()
        if t == benchmark_ticker:
            continue
        frames.append(_read_one(p, ticker=t, asset_class="ETF"))
    d = pd.concat(frames, ignore_index=True)
    d = d.sort_values(["Ticker", "Date"]).reset_index(drop=True)
    return d


def load_benchmark(path: Path, ticker: str = "SPY") -> pd.DataFrame:
    d = _read_one(Path(path), ticker=ticker, asset_class="ETF")
    return d[["Date", "Ticker", "Open", "Close", "asset_class"]].sort_values("Date").reset_index(drop=True)


def coverage(d: pd.DataFrame, start=None) -> list[dict]:
    out = []
    for t, g in d.groupby("Ticker"):
        g = g.sort_values("Date")
        r = g.Close.pct_change()
        out.append({"ticker": t, "asset_class": str(g.asset_class.iloc[0]),
                    "rows": int(len(g)), "start": str(g.Date.min().date()), "end": str(g.Date.max().date()),
                    "missing_close": int(g.Close.isna().sum()), "nonpositive_close": int((g.Close <= 0).sum()),
                    "max_abs_daily_return": float(r.abs().max()) if len(g) > 1 else None})
    return sorted(out, key=lambda x: (x["asset_class"], x["ticker"]))


def add_features(d: pd.DataFrame, benchmark: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    g = d.groupby("Ticker", sort=False)
    d["MA50"] = g.Close.transform(lambda s: s.rolling(50, min_periods=50).mean())
    d["MA200"] = g.Close.transform(lambda s: s.rolling(200, min_periods=200).mean())
    d["MA200_Slope20"] = g.MA200.transform(lambda s: s / s.shift(20) - 1)
    for n in (20, 60, 120):
        d[f"Mom{n}"] = g.Close.transform(lambda s: s / s.shift(n) - 1)
    d["Vol60"] = g.Close.transform(lambda s: s.pct_change().rolling(60, min_periods=60).std() * np.sqrt(252))
    d["DD60"] = g.Close.transform(lambda s: s / s.rolling(60, min_periods=60).max() - 1)
    d["RiskEff20"] = d.Mom20 / d.Vol60.replace(0, np.nan)
    b = benchmark[["Date", "Close"]].rename(columns={"Close": "BenchClose"}).sort_values("Date")
    d = d.merge(b, on="Date", how="left")
    for n in (20, 60, 120):
        br = b.set_index("Date").BenchClose / b.set_index("Date").BenchClose.shift(n) - 1
        d[f"Rel{n}"] = d[f"Mom{n}"] - d.Date.map(br)
    return d


def latest_snapshot(d: pd.DataFrame, signal_date) -> pd.DataFrame:
    """Last row at or before signal_date per ticker; no future rows."""
    x = d[d.Date <= pd.Timestamp(signal_date)]
    if x.empty:
        return x
    return x.sort_values(["Ticker", "Date"]).groupby("Ticker", as_index=False).tail(1)
