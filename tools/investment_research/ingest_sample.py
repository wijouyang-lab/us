"""Ingest the P2 sample universe from SEC and write a reproducible snapshot."""
from __future__ import annotations
import json
from pathlib import Path
from tools.investment_research.sec.client import SECClient
from tools.investment_research.sec.service import fetch_company

SAMPLE = [("AAPL", "Technology"), ("MSFT", "Technology"), ("GOOGL", "Technology"),
          ("AMZN", "Consumer Discretionary"), ("NVDA", "Technology"),
          ("BRK.B", "Financials"), ("JPM", "Financials"), ("PLD", "Real Estate"),
          ("RIVN", "Consumer Discretionary")]


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
