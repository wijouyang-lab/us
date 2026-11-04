"""P4.5 full 8-K scan driver. Stops without a real SEC_USER_AGENT."""
from __future__ import annotations
import json, os
from datetime import date, datetime, timezone
from pathlib import Path
from tools.investment_research.dividend.sec_filing_fetcher import FilingFetcher, config_status
from tools.investment_research.dividend.sec_fetch_manifest import load, save, upsert, complete
from tools.investment_research.sec.client import SECClient

TICKERS = ["AAPL","MSFT","GOOGL","NVDA","CRM","HD","MCD","NKE","CAT","HON","UNP","CVX",
           "NEE","DUK","JNJ","PFE","UNH","JPM","BAC","MET","PLD","O"]
CACHE = Path("data/sec/filings_p45")


def run():
    if config_status() != "SEC_USER_AGENT_CONFIGURED":
        return {"status": "CONFIGURATION_BLOCKED", "config": config_status()}
    client = SECClient("data/sec/cache"); fetcher = FilingFetcher(CACHE, os.getenv("SEC_USER_AGENT"))
    m = load(); cutoff = date.today().replace(year=date.today().year-2).isoformat()
    for t in TICKERS:
        mp = client.ticker_map(); row = mp.get(t) or mp.get(t.replace(".", "-"))
        if not row: continue
        sub = client.submissions(row["cik"]); recent = sub.get("filings", {}).get("recent", {})
        for form, dt, acc in zip(recent.get("form", []), recent.get("filingDate", []), recent.get("accessionNumber", [])):
            if form != "8-K" or not dt or dt < cutoff or acc in m["accessions"]: continue
            f = fetcher.fetch_filing(t, row["cik"], acc); upsert(m, t, acc, f); save(m)
    return {"status": "FULL_SCAN_COMPLETE" if complete(m) else "FULL_SCAN_PARTIAL",
            "accessions": len(m["accessions"]), "manifest": "data/research/sec_fetch_manifest_p45.json"}


def main():
    r = run(); print(r)


if __name__ == "__main__":
    main()
