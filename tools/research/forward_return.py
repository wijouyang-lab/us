#!/usr/bin/env python3
"""Forward-return labels from signal dates and a local OHLC panel.

Signal at close on Signal_Date; entry at the next session open; exit at the open
after exactly H additional sessions. No natural-day substitution, no fills.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd

HORIZONS = (1, 5, 10, 20, 60)
STATUS_MATURED = "MATURED"
STATUS_NOT_MATURED = "NOT_MATURED"
STATUS_MISSING = "MISSING_PRICE"


def prepare_prices(price_panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    d = price_panel.copy()
    d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
    d["Ticker"] = d["Ticker"].astype(str).str.upper().str.strip()
    d["Open"] = pd.to_numeric(d["Open"], errors="coerce")
    d = d.dropna(subset=["Date", "Ticker"])
    d = d.sort_values(["Ticker", "Date"]).drop_duplicates(["Ticker", "Date"], keep="last")
    return {t: g.reset_index(drop=True) for t, g in d.groupby("Ticker")}


def build_forward_returns(
    snapshot: pd.DataFrame,
    price_panel: pd.DataFrame,
    *,
    horizons: tuple[int, ...] = HORIZONS,
    data_source: str = "local_price_panel",
) -> pd.DataFrame:
    prices = prepare_prices(price_panel)
    rows = []
    for _, s in snapshot.iterrows():
        ticker = str(s.get("Ticker", "")).upper().strip()
        signal_raw = s.get("Technical_Date") or s.get("Scan_Date")
        signal = pd.to_datetime(signal_raw, errors="coerce")
        frame = prices.get(ticker)
        base = {
            "Signal_Date": signal.date().isoformat() if pd.notna(signal) else None,
            "Ticker": ticker,
            "Data_Source": data_source,
        }
        for h in horizons:
            rec = dict(base, Horizon=h, Entry_Date=None, Exit_Date=None,
                       Entry_Price=None, Exit_Price=None, Forward_Return=None,
                       Sample_Status=STATUS_MISSING, Missing_Reason=None)
            if pd.isna(signal):
                rec["Missing_Reason"] = "INVALID_SIGNAL_DATE"
                rows.append(rec)
                continue
            if frame is None or frame.empty:
                rec["Missing_Reason"] = "TICKER_NOT_IN_PRICE_PANEL"
                rows.append(rec)
                continue
            dates = frame["Date"].to_numpy()
            pos = int(dates.searchsorted(signal.to_datetime64(), side="right"))
            if pos >= len(frame):
                rec["Sample_Status"] = STATUS_NOT_MATURED
                rec["Missing_Reason"] = "NO_SESSION_AFTER_SIGNAL"
                rows.append(rec)
                continue
            entry = frame.iloc[pos]
            entry_date = entry["Date"]
            entry_price = entry["Open"]
            exit_pos = pos + int(h)
            if exit_pos >= len(frame):
                rec["Entry_Date"] = entry_date.date().isoformat()
                rec["Entry_Price"] = float(entry_price) if pd.notna(entry_price) else None
                rec["Sample_Status"] = STATUS_NOT_MATURED
                rec["Missing_Reason"] = "INSUFFICIENT_FUTURE_SESSIONS"
                rows.append(rec)
                continue
            exit_row = frame.iloc[exit_pos]
            exit_price = exit_row["Open"]
            rec["Entry_Date"] = entry_date.date().isoformat()
            rec["Exit_Date"] = exit_row["Date"].date().isoformat()
            rec["Entry_Price"] = float(entry_price) if pd.notna(entry_price) else None
            rec["Exit_Price"] = float(exit_price) if pd.notna(exit_price) else None
            if pd.isna(entry_price) or pd.isna(exit_price) or entry_price <= 0 or exit_price <= 0:
                rec["Missing_Reason"] = "INVALID_ENTRY_OR_EXIT_PRICE"
                rows.append(rec)
                continue
            rec["Forward_Return"] = float(exit_price / entry_price - 1.0)
            rec["Sample_Status"] = STATUS_MATURED
            rows.append(rec)
    return pd.DataFrame(rows)


def main(argv=None):
    import argparse
    import json
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot", required=True)
    p.add_argument("--price-panel", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--data-source", default="local_price_panel")
    args = p.parse_args(argv)
    snap = pd.read_csv(args.snapshot, dtype=str, keep_default_na=False)
    prices = pd.read_csv(args.price_panel, usecols=["Date", "Ticker", "Open"])
    out = build_forward_returns(snap, prices, data_source=args.data_source)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    summary = out.groupby(["Horizon", "Sample_Status"]).size().unstack(fill_value=0).to_dict(orient="index")
    print(json.dumps({str(k): {str(a): int(b) for a, b in v.items()} for k, v in summary.items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
