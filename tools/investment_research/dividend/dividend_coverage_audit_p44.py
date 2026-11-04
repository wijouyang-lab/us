"""P4.4 coverage audit. Uses cached submissions; no network if absent."""
from __future__ import annotations
import json, hashlib
from datetime import date, datetime, timezone
from pathlib import Path

TICKERS = ["AAPL","MSFT","GOOGL","NVDA","CRM","HD","MCD","NKE","CAT","HON","UNP","CVX",
           "NEE","DUK","JNJ","PFE","UNH","JPM","BAC","MET","PLD","O"]
snap = json.loads(Path("docs/research/sec_fundamentals_snapshot.json").read_text())
old = json.loads(Path("data/research/dividend_events_p43.json").read_text())
cutoff = date.today().replace(year=date.today().year - 2).isoformat()
per = {}
for t in TICKERS:
    cik = snap.get(t, {}).get("cik"); p = Path(f"data/sec/cache/submissions_{cik}.json")
    if not p.exists():
        per[t] = {"status": "SUBMISSIONS_NOT_CACHED"}; continue
    d = json.loads(p.read_text()); r = d.get("filings", {}).get("recent", {})
    n = sum(1 for form, dt in zip(r.get("form", []), r.get("filingDate", []))
            if form == "8-K" and dt and dt >= cutoff)
    per[t] = {"cik": cik, "8k_24m": n, "accessions_scanned": min(n, 5),
              "excluded_by_p43_limit": max(0, n - 5)}
summary = {"status": "CONFIGURATION_BLOCKED",
           "reason": "SEC_USER_AGENT real contact not configured; no new SEC request; p43 cache covers only 5 per company",
           "companies": len(TICKERS), "filings_seen_p43": old["summary"]["filings_seen"],
           "primary_downloaded_p43": old["summary"]["downloaded"],
           "candidate_events_p43": old["summary"]["candidates"],
           "verified_p43": old["summary"]["verified"],
           "full_scan_completed": False,
           "total_8k_24m_cached": sum(x.get("8k_24m",0) for x in per.values()),
           "accessions_scanned_p43_limit": sum(x.get("accessions_scanned",0) for x in per.values()),
           "excluded_by_limit": sum(x.get("excluded_by_p43_limit",0) for x in per.values())}
Path("data/research/dividend_coverage_p44.json").write_text(json.dumps(
    {"summary": summary, "per_company": per}, indent=2), encoding="utf-8")
# false positive register: URL-only evidence, no raw document downloaded
url = "https://www.sec.gov/Archives/edgar/data/753308/000110465926100476/tm2623831d1_8k.htm"
fp = [{"ticker": "NEE", "amount": 67.75, "reason": "FALSE_POSITIVE_NON_DIVIDEND_PRICE_TARGET",
       "source_url": url, "evidence_sha256": hashlib.sha256(url.encode()).hexdigest(),
       "evidence_status": "URL_ONLY_NOT_DOWNLOADED", "is_event": False}]
Path("data/research/dividend_false_positives_p44.json").write_text(json.dumps(fp, indent=2), encoding="utf-8")
print(summary)
