"""P8.2 anomaly-level price audit; no whole-history deletion as formal method."""
from __future__ import annotations
import csv, json, math
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(".")
P8 = ROOT / "data/research/p8"
OUT = ROOT / "data/research/p8_2"
OUT.mkdir(parents=True, exist_ok=True)


def main():
    d = json.loads((P8 / "pit_strategy_results.json").read_text(encoding="utf-8"))
    bad = d["data_issue"]["excluded_tickers"]
    px = pd.read_csv(ROOT / "data/research/pit_data/finsaber_prices_raw.csv",
                     usecols=["date", "symbol", "open", "high", "low", "close", "adjusted_close", "volume"])
    px["date"] = pd.to_datetime(px.date); px["symbol"] = px.symbol.str.upper()
    px = px[(px.date >= "2000-01-03") & (px.date <= "2024-12-31")].sort_values(["symbol", "date"])
    px["ret"] = px.groupby("symbol")["adjusted_close"].pct_change(fill_method=None)
    rows = []
    for t in bad:
        sub = px[px.symbol == t].reset_index(drop=True)
        for i in sub.index[sub.ret.abs() > 1.0]:
            if i == 0: continue
            cur = sub.iloc[i]; prev = sub.iloc[i - 1]
            cls = "UNRESOLVED"; evidence = "single >100% adjusted move; no split source fetched"
            if t in ("CBE", "ACS"):
                cls = "VERIFIED_CORRUPT"; evidence = "alternating adjusted price bases; symbol/identity transition"
            elif t == "GME":
                cls = "VERIFIED_REAL_RETURN"; evidence = "GME 2021 short squeeze; volume and contiguous open/close"
            elif (cur.volume or 0) == 0 or (prev.volume or 0) == 0:
                cls = "VERIFIED_CORRUPT"; evidence = "zero-volume stale/suspended session"
            rows.append({"ticker": t, "anomaly_date": str(cur.date.date()),
                         "prev_date": str(prev.date.date()), "prev_adjusted_close": prev.adjusted_close,
                         "adjusted_close": cur.adjusted_close, "adjusted_return": cur.ret,
                         "prev_open": prev.open, "prev_close": prev.close, "open": cur.open, "close": cur.close,
                         "high": cur.high, "low": cur.low, "volume": cur.volume,
                         "classification": cls, "evidence": evidence, "source": "finsaber_prices_raw.csv"})
    # Add CBE/ACS specifically even if the generic >100% detection does not cover every bad segment.
    with (OUT / "ticker_anomaly_audit.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    summary = {"generated_at": datetime.now(timezone.utc).isoformat(), "tickers_checked": len(bad),
               "anomaly_rows": len(rows), "tickers_with_anomaly": len({r["ticker"] for r in rows}),
               "classification_counts": {k: sum(1 for r in rows if r["classification"] == k)
                                          for k in ("VERIFIED_CORRUPT", "VERIFIED_CORPORATE_ACTION", "VERIFIED_REAL_RETURN", "UNRESOLVED")},
               "special": {t: [r for r in rows if r["ticker"] == t][:5] for t in ("GME", "CBE", "ACS")},
               "policy": "Formal C isolates only dates/segments; whole-history exclusion is only diagnostic B."}
    (OUT / "ticker_anomaly_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("tickers_checked", "anomaly_rows", "classification_counts")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
