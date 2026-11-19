"""P8.2 PIT coverage with full membership denominator."""
from __future__ import annotations
import csv, json
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(".")
OUT = ROOT / "data/research/p8_2"


def main():
    m = pd.read_csv(ROOT / "data/research/historical_universe/sp500_daily.csv")
    m["date"] = pd.to_datetime(m.date).dt.date
    m = m.drop_duplicates("date").sort_values("date")
    m = m[(m.date >= date(2000, 1, 3)) & (m.date <= date(2024, 12, 31))]
    px = pd.read_csv(ROOT / "data/research/pit_data/finsaber_prices_raw.csv",
                     usecols=["date", "symbol", "adjusted_close"])
    px["date"] = pd.to_datetime(px.date).dt.date
    px["symbol"] = px.symbol.str.upper()
    px = px[(px.date >= date(2000, 1, 3)) & (px.date <= date(2024, 12, 31))]
    valid = {(r.date, r.symbol) for r in px.itertuples() if pd.notna(r.adjusted_close) and r.adjusted_close > 0}
    anom = defaultdict(set)
    with (OUT / "ticker_anomaly_audit.csv").open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            anom[r["ticker"]].add(date.fromisoformat(r["anomaly_date"]))
    by_year = defaultdict(lambda: {"member_days": 0, "valid": 0, "verified": 0, "quarantined": 0, "unknown": 0})
    by_t = defaultdict(lambda: {"member_days": 0, "valid": 0, "verified": 0, "quarantined": 0})
    total = {"member_days": 0, "valid": 0, "verified": 0, "quarantined": 0, "unknown": 0}
    for row in m.itertuples():
        d = row.date
        members = {x.strip().upper() for x in str(row.tickers).split(",") if x.strip()}
        for t in members:
            total["member_days"] += 1; by_year[d.year]["member_days"] += 1; by_t[t]["member_days"] += 1
            if (d, t) not in valid:
                total["unknown"] += 1; by_year[d.year]["unknown"] += 1
            else:
                total["valid"] += 1; by_year[d.year]["valid"] += 1; by_t[t]["valid"] += 1
                if d in anom[t]:
                    total["quarantined"] += 1; by_year[d.year]["quarantined"] += 1; by_t[t]["quarantined"] += 1
                else:
                    total["verified"] += 1; by_year[d.year]["verified"] += 1; by_t[t]["verified"] += 1
    def pct(a, b): return round(a / b, 8) if b else None
    summary = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "denominator": "ALL effective-dated S&P member-days, 2000-01-03..2024-12-31",
               "totals": {**total, "original_coverage": pct(total["valid"], total["member_days"]),
                          "repaired_coverage": pct(total["verified"], total["member_days"]),
                          "quarantine_rate": pct(total["quarantined"], total["member_days"]),
                          "unknown_rate": pct(total["unknown"], total["member_days"])},
               "policy": "No member is removed before computing the denominator."}
    (OUT / "pit_coverage_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with (OUT / "pit_coverage_by_year.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["year", "member_days", "valid", "verified", "quarantined", "unknown", "original_coverage", "repaired_coverage"]); w.writeheader()
        for y in sorted(by_year):
            x = by_year[y]; w.writerow({"year": y, **x, "original_coverage": pct(x["valid"], x["member_days"]), "repaired_coverage": pct(x["verified"], x["member_days"])})
    with (OUT / "pit_coverage_by_ticker.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ticker", "member_days", "valid", "verified", "quarantined", "original_coverage", "repaired_coverage"]); w.writeheader()
        for t in sorted(by_t):
            x = by_t[t]; w.writerow({"ticker": t, **x, "original_coverage": pct(x["valid"], x["member_days"]), "repaired_coverage": pct(x["verified"], x["member_days"])})
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
