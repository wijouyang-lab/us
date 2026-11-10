#!/usr/bin/env python3
"""Generate full forward labels for the factor panel using vectorized session indices."""
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd

from tools.research.forward_return import prepare_prices, STATUS_MATURED, STATUS_MISSING, STATUS_NOT_MATURED


def labels_for_horizon(snapshot: pd.DataFrame, price_panel: pd.DataFrame, h: int) -> pd.DataFrame:
    prices = prepare_prices(price_panel)
    out = []
    for ticker, g in snapshot.groupby("Ticker", sort=True):
        g = g.sort_values("Signal_Date")
        frame = prices.get(ticker)
        if frame is None or frame.empty:
            for _, row in g.iterrows():
                out.append((row["Ticker"], row["Signal_Date"], h, None, None, None, None, STATUS_MISSING, "TICKER_NOT_IN_PRICE_PANEL"))
            continue
        pv = frame["Date"].to_numpy()
        op = frame["Open"].to_numpy()
        for _, row in g.iterrows():
            dt = row["Signal_Date"]
            pos = int(np.searchsorted(pv, np.datetime64(dt), side="right"))
            if pos >= len(pv):
                out.append((ticker, dt, h, None, None, None, None, STATUS_NOT_MATURED, "NO_SESSION_AFTER_SIGNAL"))
                continue
            exit_pos = pos + h
            if exit_pos >= len(pv):
                out.append((ticker, dt, h, str(pd.Timestamp(pv[pos]).date()), None, float(op[pos]), None, STATUS_NOT_MATURED, "INSUFFICIENT_FUTURE_SESSIONS"))
                continue
            entry, exit_px = op[pos], op[exit_pos]
            if pd.isna(entry) or pd.isna(exit_px) or entry <= 0 or exit_px <= 0:
                out.append((ticker, dt, h, str(pd.Timestamp(pv[pos]).date()), str(pd.Timestamp(pv[exit_pos]).date()), None, None, STATUS_MISSING, "INVALID_ENTRY_OR_EXIT_PRICE"))
                continue
            out.append((ticker, dt, h, str(pd.Timestamp(pv[pos]).date()), str(pd.Timestamp(pv[exit_pos]).date()),
                        float(entry), float(exit_px), STATUS_MATURED, None))
    df = pd.DataFrame(out, columns=["Ticker", "Signal_Date", "Horizon", "Entry_Date", "Exit_Date",
                                    "Entry_Price", "Exit_Price", "Sample_Status", "Missing_Reason"])
    df["Forward_Return"] = df["Exit_Price"] / df["Entry_Price"] - 1
    df["Data_Source"] = "local_price10y_1028.csv"
    return df


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--factors", required=True)
    p.add_argument("--price-panel", required=True)
    p.add_argument("--out-dir", required=True)
    args = p.parse_args(argv)
    f = pd.read_parquet(args.factors, columns=["Ticker", "Date"])
    f["Signal_Date"] = pd.to_datetime(f["Date"])
    f = f.drop(columns=["Date"])
    p = pd.read_csv(args.price_panel, usecols=["Date", "Ticker", "Open"])
    p["Date"] = pd.to_datetime(p["Date"])
    p["Ticker"] = p["Ticker"].astype(str).str.upper()
    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    for h in (1, 5, 10, 20, 60):
        df = labels_for_horizon(f, p, h)
        df.to_parquet(out / f"labels_{h}d.parquet", index=False)
        print(h, df["Sample_Status"].value_counts().to_dict())


if __name__ == "__main__":
    raise SystemExit(main())
