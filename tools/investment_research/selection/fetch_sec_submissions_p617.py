"""P6.17 SEC submissions filing-history audit for the 144 Top50 tickers.

Recent periodic filings are fetched from SEC Submissions (free). 6-K content is
never treated as a confirmed financial update; it is marked unverified.
"""
from __future__ import annotations
import argparse, csv, json, time
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import requests

ROOT = Path("data/universe/selection")
INPUTS = Path("data/universe/selection_inputs")
CLASS = INPUTS / "issuer_classification_p615.csv"
AS_OF = date(2026, 11, 5)
FORMS = {"10-K", "10-Q", "20-F", "40-F", "6-K"}
UA = "wijouyang-us-research/1.0 (contact: project-owner)"
OUT = ROOT / "sec_filing_history_p617.csv"
AUDIT = ROOT / "filing_freshness_audit_p617.csv"
SUMMARY = ROOT / "filing_freshness_summary_p617.json"


def read(p):
    b = p.read_bytes()[:2]
    with p.open(encoding="utf-16" if b in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def top_rows():
    out = []
    for name in ("value_top50.csv", "quality_top50.csv", "garp_top50.csv"):
        for r in read(ROOT / name):
            out.append((name.split("_")[0], r))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--audit", type=Path, default=AUDIT)
    ap.add_argument("--summary", type=Path, default=SUMMARY)
    a = ap.parse_args()
    cls = {r["ticker"]: r for r in read(CLASS)}
    tops = top_rows()
    by_ticker = defaultdict(list)
    for kind, r in tops: by_ticker[r["ticker"]].append((kind, r))
    history = []; audits = []; errors = 0
    for ticker in sorted(by_ticker):
        cik = (cls.get(ticker, {}).get("cik") or by_ticker[ticker][0][1].get("cik") or "").zfill(10)
        if not cik:
            for kind, r in by_ticker[ticker]:
                audits.append({"ticker": ticker, "cik": "", "ranking": kind, "audit_status": "FILING_DATA_BLOCKED",
                               "reason": "CIK_MISSING", "stored_period": r.get("financial_period") or r.get("latest_period", ""),
                               "stored_filed": r.get("filed", ""), "latest_periodic_form": "", "latest_periodic_filed": "",
                               "latest_6k_filed": ""})
            continue
        try:
            url = f"https://data.sec.gov/submissions/CIK{cik}.json"
            resp = requests.get(url, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=30)
            if resp.status_code == 429:
                raise RuntimeError("HTTP_429_STOP")
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP_{resp.status_code}")
            data = resp.json()
            recent = data.get("filings", {}).get("recent", {})
            forms = recent.get("form", []); fdates = recent.get("filingDate", [])
            rdates = recent.get("reportDate", []); accs = recent.get("accessionNumber", [])
            ticker_history = []
            for i, form in enumerate(forms):
                if form not in FORMS: continue
                fd = fdates[i] if i < len(fdates) else ""
                if not fd or fd > AS_OF.isoformat(): continue
                row = {"ticker": ticker, "cik": cik, "form": form, "filingDate": fd,
                       "reportDate": rdates[i] if i < len(rdates) else "",
                       "accessionNumber": accs[i] if i < len(accs) else "",
                       "source_url": url, "retrieved_at": datetime.now(timezone.utc).isoformat()}
                ticker_history.append(row); history.append(row)
            for kind, r in by_ticker[ticker]:
                classified = read(CLASS) if False else None
                stored_period = r.get("financial_period") or r.get("latest_period", "")
                stored_filed = r.get("filed", "")
                periodic = [x for x in ticker_history if x["form"] in ("10-K", "10-Q", "20-F", "40-F")]
                sixk = [x for x in ticker_history if x["form"] == "6-K"]
                later_periodic = [x for x in periodic if (stored_filed and x["filingDate"] > stored_filed)
                                  or (stored_period and x["reportDate"] and x["reportDate"] > stored_period)]
                later_6k = [x for x in sixk if stored_filed and x["filingDate"] > stored_filed]
                latest_periodic = max(periodic, key=lambda x: x["filingDate"], default=None)
                latest_6k = max(sixk, key=lambda x: x["filingDate"], default=None)
                if later_periodic:
                    status = "SUPERSEDED_BY_NEW_PERIODIC_FILING"; reason = "LATER_10K_10Q_20F_40F"
                elif later_6k:
                    status = "6K_LATER_NOT_VERIFIED"; reason = "6K_CONTENT_NOT_CONFIRMED"
                else:
                    status = "FILING_HISTORY_CONFIRMED"; reason = "NO_LATER_PERIODIC_OR_6K"
                audits.append({"ticker": ticker, "cik": cik, "ranking": kind,
                               "stored_period": stored_period, "stored_filed": stored_filed,
                               "stored_accession": r.get("accn", ""),
                               "latest_periodic_form": latest_periodic["form"] if latest_periodic else "",
                               "latest_periodic_filed": latest_periodic["filingDate"] if latest_periodic else "",
                               "latest_periodic_report": latest_periodic["reportDate"] if latest_periodic else "",
                               "latest_periodic_accession": latest_periodic["accessionNumber"] if latest_periodic else "",
                               "latest_6k_filed": latest_6k["filingDate"] if latest_6k else "",
                               "later_periodic_count": len(later_periodic), "later_6k_count": len(later_6k),
                               "audit_status": status, "reason": reason,
                               "source_url": url})
        except Exception as exc:
            errors += 1
            for kind, r in by_ticker[ticker]:
                audits.append({"ticker": ticker, "cik": cik, "ranking": kind, "audit_status": "FILING_DATA_BLOCKED",
                               "reason": f"{type(exc).__name__}:{str(exc)[:100]}",
                               "stored_period": r.get("financial_period") or r.get("latest_period", ""),
                               "stored_filed": r.get("filed", ""), "latest_periodic_form": "",
                               "latest_periodic_filed": "", "latest_6k_filed": ""})
        time.sleep(0.16)
    hist_fields = ["ticker","cik","form","filingDate","reportDate","accessionNumber","source_url","retrieved_at"]
    with a.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=hist_fields); w.writeheader(); w.writerows(history)
    audit_fields = ["ticker","cik","ranking","stored_period","stored_filed","stored_accession","latest_periodic_form","latest_periodic_filed",
                    "latest_periodic_report","latest_periodic_accession","latest_6k_filed","later_periodic_count",
                    "later_6k_count","audit_status","reason","source_url"]
    with a.audit.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=audit_fields); w.writeheader(); w.writerows(audits)
    from collections import Counter
    summary = {"generated_at": datetime.now(timezone.utc).isoformat(), "as_of": AS_OF.isoformat(),
               "requested_tickers": len(by_ticker), "history_rows": len(history), "audit_rows": len(audits),
               "api_errors": errors, "status_counts": dict(Counter(x["audit_status"] for x in audits)),
               "superseded_tickers": sorted({x["ticker"] for x in audits if x["audit_status"] == "SUPERSEDED_BY_NEW_PERIODIC_FILING"}),
               "sixk_unverified_tickers": sorted({x["ticker"] for x in audits if x["audit_status"] == "6K_LATER_NOT_VERIFIED"}),
               "forms": dict(Counter(x["form"] for x in history)),
               "note": "6-K is not treated as a confirmed financial update; no financial content parsing. API failures are DATA_BLOCKED."}
    a.summary.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
