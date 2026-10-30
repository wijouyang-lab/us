#!/usr/bin/env python3
"""Event-factor panel from SEC filing events.

Fundamental/macro/news factors are emitted with UNAVAILABLE_DATA when no
verified source is supplied; no values are fabricated.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from tools.research.event_data import next_trading_session

FUNDAMENTAL_FACTORS = ["Revenue_Growth", "EPS_Growth", "Gross_Margin_Change",
                       "Operating_Margin_Change", "FCF_Change"]
MACRO_FACTORS = ["Macro_Rate_Change", "CPI_Surprise", "Payroll_Surprise", "VIX_Regime"]


def build(events: pd.DataFrame, calendar: list | None = None) -> pd.DataFrame:
    d = events.copy()
    d["published_at"] = pd.to_datetime(d["acceptance_datetime"], errors="coerce", utc=True)
    d["event_date"] = pd.to_datetime(d["filing_date"], errors="coerce").dt.date.astype(str)
    d["event_id"] = d["accession"].astype(str)
    d["event_type"] = "filing"
    d["event_subtype"] = d["form"]
    d["earnings"] = d["form"].isin(["10-Q", "10-K"]) | d["items"].fillna("").str.contains("2.02")
    d["management_change"] = d["items"].fillna("").str.contains("5.02")
    d["SEC_8K_Event_Count"] = 0
    for t, g in d[d.form.eq("8-K")].groupby("ticker"):
        idx = g.index
        for i in idx:
            dt = d.loc[i, "published_at"]
            if pd.isna(dt):
                continue
            window = d.loc[idx, "published_at"]
            d.loc[i, "SEC_8K_Event_Count"] = int(((window >= dt - pd.Timedelta(days=20)) & (window <= dt)).sum())
    cal = calendar or sorted(pd.bdate_range("2019-01-01", "2027-01-01"))
    d["trade_date"] = d["published_at"].apply(lambda x: next_trading_session(x.isoformat() if pd.notna(x) else None, cal))
    d["Earnings_Release_Indicator"] = d["earnings"].astype(int)
    d["Management_Change_Indicator"] = d["management_change"].astype(int)
    for f in FUNDAMENTAL_FACTORS + MACRO_FACTORS:
        if f not in d:
            d[f] = None
    d["pit_eligible"] = False
    d["timestamp_confidence"] = "official_acceptance_time_not_first_public"
    d["source_confidence"] = "official_sec_submissions"
    return d[["event_id", "ticker", "cik", "event_type", "event_subtype", "published_at", "event_date",
              "trade_date", "SEC_8K_Event_Count", "Earnings_Release_Indicator",
              "Management_Change_Indicator"] + FUNDAMENTAL_FACTORS + MACRO_FACTORS +
             ["source_confidence", "timestamp_confidence", "pit_eligible"]]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--events", required=True)
    p.add_argument("--calendar", default=None)
    p.add_argument("--output", required=True)
    a = p.parse_args(argv)
    events = pd.read_json(a.events) if a.events.endswith(".json") else pd.read_csv(a.events)
    cal = None
    if a.calendar:
        cal = sorted(pd.to_datetime(pd.read_csv(a.calendar, usecols=["Date"]).Date).unique())
    out = build(events, cal)
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.output, index=False)
    summary = {"rows": len(out), "tickers": int(out.ticker.nunique()),
               "earnings_events": int(out.Earnings_Release_Indicator.sum()),
               "eight_k_events": int(out.event_subtype.eq("8-K").sum()),
               "management_events": int(out.Management_Change_Indicator.sum()),
               "unavailable_fundamental": {f: int(out[f].isna().sum()) for f in FUNDAMENTAL_FACTORS},
               "unavailable_macro": {f: int(out[f].isna().sum()) for f in MACRO_FACTORS},
               "pit_eligible": 0}
    Path(a.output).with_suffix(".summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
