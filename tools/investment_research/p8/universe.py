"""P8 universe inventory and PIT tier declaration."""
from __future__ import annotations
import csv, json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(".")
OUT = ROOT / "data/research/p8"


def main():
    rows = []
    with (ROOT / "data/research/historical_universe/sp500_daily.csv").open(encoding="utf-8", newline="") as f:
        m = list(csv.DictReader(f))
    last = m[-1]
    for t in sorted({x.strip() for x in last["tickers"].split(",") if x.strip()}):
        rows.append({"ticker": t, "index": "SP500", "index_source": "historical_universe/sp500_daily.csv",
                     "membership_effective_date": last["date"], "membership_end_date": "",
                     "current_status": "CURRENT_LAST_AVAILABLE_SNAPSHOT", "historical_status": "PIT_MEMBERSHIP_AVAILABLE"})
    for index in ("NASDAQ100", "DOW30"):
        rows.append({"ticker": "", "index": index, "index_source": "NOT_FOUND", "membership_effective_date": "",
                     "membership_end_date": "", "current_status": "DATA_BLOCKED",
                     "historical_status": "DATA_BLOCKED_NO_INTERVAL_FILE"})
    (OUT / "universe_membership.csv").parent.mkdir(parents=True, exist_ok=True)
    with (OUT / "universe_membership.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    summary = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "sp500_last_snapshot": last["date"], "sp500_current_rows": len(rows) - 2,
               "sp500_historical": "EFFECTIVE_DATED_INTERVALS_AVAILABLE",
               "nasdaq100": "DATA_BLOCKED_NO_INTERVAL_FILE",
               "dow30": "DATA_BLOCKED_NO_INTERVAL_FILE",
               "price_panel_end": "2024-12-31",
               "pit_tiers": {"current_decision": "last available S&P snapshot + current yfinance; not used for historical return",
                              "historical_backtest": "effective-dated S&P membership + 2000-2024 price panel"},
               "note": "NDX/DJI are not silently replaced by current lists."}
    (OUT / "universe_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
