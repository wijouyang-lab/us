"""Ingest the P2 sample universe from SEC and write a reproducible snapshot."""
from __future__ import annotations
import json
from pathlib import Path
from tools.investment_research.sec.client import SECClient
from tools.investment_research.sec.service import fetch_company

SAMPLE = [
    ("AAPL", None),("MSFT", None),("GOOGL", None),("NVDA", None),
    ("CRM", None),("ADBE", None),("AMZN", None),
    ("HD", None),("MCD", None),("NKE", None),
    ("CAT", None),("HON", None),("UNP", None),
    ("XOM", None),("CVX", None),("NEE", None),("DUK", None),
    ("JNJ", None),("PFE", None),("UNH", None),("MRNA", None),
    ("JPM", None),("BAC", None),("BRK.B", None),("MET", None),
    ("PLD", None),("O", None),("RIVN", None)]


def main():
    c = SECClient("data/sec/cache")
    out = {}
    for ticker, sector in SAMPLE:
        try:
            a = fetch_company(c, ticker, sector=sector)
            out[ticker] = a
            v = a.get("value", {})
            print(ticker, a.get("facts_count"), v.get("revenue", {}).get("value"),
                  v.get("net_income", {}).get("value"))
        except Exception as e:
            out[ticker] = {"ticker": ticker, "status": "ERROR", "error": str(e)}
            print(ticker, "ERROR", e)
    p = Path("docs/research/sec_fundamentals_snapshot.json")
    p.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print("saved", p, len(out))


if __name__ == "__main__":
    main()
