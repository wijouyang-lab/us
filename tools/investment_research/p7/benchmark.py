"""P7 benchmark snapshot: SPY/QQQ/IWM plus equal-weight strategy reference."""
from __future__ import annotations
import csv, json, tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import yfinance as yf

OUT = Path("data/universe/p7")
AS_OF = date(2026, 11, 5)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(tempfile.mkdtemp(prefix="yf-p7-bench-"))
    data = yf.download(["SPY", "QQQ", "IWM"], period="6mo", interval="1d",
                       auto_adjust=False, actions=False, threads=False, progress=False, group_by="ticker")
    rows = []
    for t in ("SPY", "QQQ", "IWM"):
        frame = data[t] if hasattr(data.columns, "levels") else data
        frame = frame.dropna(subset=["Close"]).copy()
        frame.index = [x.date() for x in frame.index]
        frame = frame[[d <= AS_OF for d in frame.index]]
        for d in frame.index:
            rows.append({"date": d.isoformat(), "ticker": t, "close": float(frame.loc[d, "Close"]),
                         "source": "yfinance", "adjustment": "UNADJUSTED_CLOSE",
                         "retrieved_at": datetime.now(timezone.utc).isoformat(), "currency": "USD"})
    # No strategy history yet: equal-weight is a target reference, not a return.
    rows.append({"date": AS_OF.isoformat(), "ticker": "EQUAL_WEIGHT", "close": "", "source": "P7_TARGET_REFERENCE",
                 "adjustment": "NOT_APPLICABLE", "retrieved_at": datetime.now(timezone.utc).isoformat(), "currency": "USD"})
    with (OUT / "benchmark_snapshot.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    summary = {"generated_at": datetime.now(timezone.utc).isoformat(), "as_of": AS_OF.isoformat(),
               "source": "yfinance", "tickers": ["SPY", "QQQ", "IWM"],
               "rows": len(rows), "status": "CURRENT_SNAPSHOT_ONLY",
               "note": "No historical strategy return; equal-weight is PENDING_TARGET_REFERENCE."}
    (OUT / "benchmark_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
