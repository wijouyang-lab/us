import json
from pathlib import Path

import pandas as pd

snap = pd.read_csv("data/_download/snap/research_factor_snapshots_sp500_pit_10y.csv", usecols=["Technical_Date", "Ticker", "Price"])
snap["date"] = pd.to_datetime(snap.Technical_Date)
ev = pd.read_csv("data/research/macro_cross_sectional/bls_macro_events.csv")
ev["d"] = pd.to_datetime(ev.release_date)
# Count events with >= 20 names having a price on the release date.
counts = []
for _, e in ev[ev.d >= "2017-01-01"].iterrows():
    n = snap[snap.date == e.d].Ticker.nunique()
    counts.append((e.event_type, n))
df = pd.DataFrame(counts, columns=["family", "n"])
audit = {
    "snapshot": {"rows": int(len(snap)), "tickers": int(snap.Ticker.nunique()),
                 "start": str(snap.date.min().date()), "end": str(snap.date.max().date()),
                 "columns_checked": ["Price"], "has_open_high_low_close": False,
                 "has_adj_close": False, "has_split_adjustment": False,
                 "has_dividend_adjustment": False, "pit_membership_verified": False},
    "events_2017_plus": {"cpi": int(sum(1 for f, _ in counts if f == "cpi")),
                         "employment": int(sum(1 for f, _ in counts if f == "employment"))},
    "min_names_per_event": int(df.n.min()) if len(df) else 0,
    "median_names_per_event": float(df.n.median()) if len(df) else 0,
    "events_with_20_names": int((df.n >= 20).sum()),
    "verdict": "PARTIAL_PRICE_ONLY",
    "blockers": [
        "Price is unadjusted close; no Adj Close, split or dividend adjustment.",
        "Historical S&P 500 membership and delisted tickers are not fully PIT verified.",
        "No Open/High/Low; cannot model next-open execution or intrabar timing.",
        "Macro releases are date-only; exact embargo time is unavailable.",
    ],
}
Path("data/research/macro_cross_sectional/p12_5_2_price_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
print(json.dumps(audit, indent=2))
