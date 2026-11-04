"""P4.5 full scan with expected inventory, retries and text-scan completion."""
from __future__ import annotations
import json, os
from datetime import date
from pathlib import Path
from tools.investment_research.dividend.sec_filing_fetcher import FilingFetcher, config_status
from tools.investment_research.dividend.sec_fetch_manifest import (
    load, save, set_expected, upsert, should_attempt, mark_text_scanned, complete)
from tools.investment_research.sec.client import SECClient

TICKERS = ["AAPL","MSFT","GOOGL","NVDA","CRM","HD","MCD","NKE","CAT","HON","UNP","CVX",
           "NEE","DUK","JNJ","PFE","UNH","JPM","BAC","MET","PLD","O"]
CACHE = Path("data/sec/filings_p45")


def build_inventory(client):
    cutoff = date.today().replace(year=date.today().year-2).isoformat()
    out = []
    mp = client.ticker_map()
    for t in TICKERS:
        row = mp.get(t) or mp.get(t.replace(".", "-"))
        if not row: continue
        sub = client.submissions(row["cik"]); recent = sub.get("filings", {}).get("recent", {})
        for form, dt, acc in zip(recent.get("form", []), recent.get("filingDate", []), recent.get("accessionNumber", [])):
            if form == "8-K" and dt and dt >= cutoff:
                out.append({"ticker": t, "cik": row["cik"], "accession": acc, "filing_date": dt})
    return out


def scan_text(entry):
    ok = False
    for d in entry.get("documents", []):
        p = d.get("path")
        if p and Path(p).exists():
            Path(p).read_text(errors="ignore"); ok = True
    return ok


def run():
    if config_status() != "SEC_USER_AGENT_CONFIGURED":
        return {"status": "CONFIGURATION_BLOCKED", "config": config_status()}
    client = SECClient("data/sec/cache"); fetcher = FilingFetcher(CACHE, os.getenv("SEC_USER_AGENT"))
    m = load(); inv = build_inventory(client); set_expected(m, inv); save(m)
    for e in inv:
        acc = e["accession"]
        if not should_attempt(m, acc):
            continue
        f = fetcher.fetch_filing(e["ticker"], e["cik"], acc)
        upsert(m, e["ticker"], acc, f)
        if f.get("status_text") in ("FETCHED_COMPLETE", "FETCHED_PARTIAL") and scan_text(f):
            mark_text_scanned(m, acc)
        save(m)
    if complete(m):
        status = "FULL_SCAN_COMPLETE"
    elif any(a.get("status") not in ("NOT_ATTEMPTED", None) for a in m["accessions"].values()):
        status = "FULL_SCAN_ATTEMPTED_WITH_FAILURES"
    else:
        status = "FULL_SCAN_PARTIAL"
    return {"status": status, "expected": len(inv), "recorded": len(m["accessions"]),
            "complete": complete(m), "manifest": "data/research/sec_fetch_manifest_p45.json"}


def main():
    print(run())


if __name__ == "__main__":
    main()
