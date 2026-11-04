"""P4.3 SEC 8-K dividend-event candidate collector. No fabricated events."""
from __future__ import annotations
import json, os, re
from datetime import date, datetime, timezone
from pathlib import Path
from tools.investment_research.dividend.evidence_registry import event_id
from tools.investment_research.dividend.sec_filing_fetcher import FilingFetcher
from tools.investment_research.sec.client import SECClient

TICKERS = ["AAPL","MSFT","GOOGL","NVDA","CRM","HD","MCD","NKE","CAT","HON","UNP","CVX",
           "NEE","DUK","JNJ","PFE","UNH","JPM","BAC","MET","PLD","O"]
KEY = re.compile(r"(cash dividend|quarterly dividend|dividend.*per share|declared.*dividend)", re.I)
AMOUNT = re.compile(r"\$\s?([0-9]+\.[0-9]{2,4})\s*(?:per share|per common share)", re.I)


def collect(months=24, per_company=5):
    client = SECClient("data/sec/cache")
    fetcher = FilingFetcher(Path("data/sec/filings_p43"), os.getenv("SEC_USER_AGENT",""))
    cutoff = date.today().replace(year=date.today().year - (1 if months <= 12 else 2))
    summary = {"companies": len(TICKERS), "filings_seen": 0, "downloaded": 0, "failed": 0,
               "relevant_8k": 0, "candidates": 0, "verified": 0,
               "partially_verified": 0, "conflicted": 0, "status": "NO_MATCHING_FILING"}
    events = []
    mp = client.ticker_map()
    for t in TICKERS:
        m = mp.get(t) or mp.get(t.replace(".","-"))
        if not m: continue
        cik = m["cik"]; sub = client.submissions(cik)
        recent = sub.get("filings", {}).get("recent", {})
        forms = recent.get("form", []); dates = recent.get("filingDate", [])
        accs = recent.get("accessionNumber", [])
        picked = [(dt, acc) for form, dt, acc in zip(forms, dates, accs)
                  if form == "8-K" and dt and dt >= cutoff.isoformat()]
        summary["filings_seen"] += len(picked)
        for dt, acc in picked[:per_company]:
            f = fetcher.fetch_filing(t, cik, acc)
            if f.get("status_text") != "FETCHED":
                summary["failed"] += 1; continue
            summary["downloaded"] += 1
            primary = f.get("primary") or {}
            text = ""
            if primary.get("path"):
                try: text = Path(primary["path"]).read_text(errors="ignore")
                except Exception: pass
            text = re.sub(r"<[^>]+>", " ", text); text = re.sub(r"\s+", " ", text)
            if not KEY.search(text): continue
            summary["relevant_8k"] += 1
            amt = None
            for cand in AMOUNT.finditer(text):
                ctx = text[max(0, cand.start()-160):cand.end()+160].lower()
                if "dividend" in ctx and "per share" in ctx and "preferred" not in ctx:
                    amt = cand; break
            if not amt: continue
            summary["candidates"] += 1
            events.append({"event_id": event_id(ticker=t, event_type="DECLARED", event_date=dt,
                    source_url=f.get("index_url"), evidence_sha256=primary.get("sha256","")),
                  "ticker": t, "cik": cik, "event_type": "DECLARED",
                  "declared_per_share": float(amt.group(1)), "currency": "USD",
                  "frequency": None, "announcement_date": dt, "ex_date": None,
                  "record_date": None, "payment_date": None,
                  "source_url": f.get("index_url"), "source_type": "SEC 8-K",
                  "accession_number": acc, "evidence_sha256": primary.get("sha256",""),
                  "retrieved_at": datetime.now(timezone.utc).isoformat(),
                  "verification_status": "PARTIALLY_VERIFIED",
                  "evidence_notes": "8-K text contains per-share dividend; only filing date parsed"})
            summary["partially_verified"] += 1
    if events: summary["status"] = "EVENT_CANDIDATES_FOUND"
    Path("data/research/dividend_events_p43.json").write_text(json.dumps(
        {"summary": summary, "events": events}, indent=2), encoding="utf-8")
    return summary


def main():
    print(collect())


if __name__ == "__main__":
    main()


TYPES = {"DECLARED","EX_DATE","RECORD_DATE","PAYMENT_DATE","INCREASED","REDUCED","SUSPENDED","RESUMED"}

def normalize(rec: dict) -> dict:
    from tools.investment_research.dividend.evidence_registry import validate_source, validate_date
    for k in ("ticker","cik","event_type","announcement_date","source_url","source_type","evidence_sha256"):
        if not rec.get(k): raise ValueError(f"missing {k}")
    if rec["event_type"] not in TYPES: raise ValueError("bad event type")
    validate_source(rec["source_url"]); validate_date(rec["announcement_date"], "announcement_date")
    for k in ("ex_date","record_date","payment_date"): validate_date(rec.get(k), k)
    if rec.get("event_type") == "EX_DATE" and not rec.get("ex_date"): rec["ex_date_status"] = "EX_DATE_UNAVAILABLE"
    rec["event_id"] = rec.get("event_id") or event_id(ticker=rec["ticker"], event_type=rec["event_type"],
        event_date=rec["announcement_date"], source_url=rec["source_url"], evidence_sha256=rec["evidence_sha256"])
    rec["verification_status"] = rec.get("verification_status", "SOURCE_FETCHED")
    if rec["verification_status"] == "VERIFIED" and not rec.get("evidence_notes"): rec["verification_status"] = "PARTIALLY_VERIFIED"
    return rec

def dedupe(rows: list[dict]) -> list[dict]:
    out = {}
    for r in rows:
        n = normalize(r)
        key = (n["ticker"].upper(), n["event_type"], n.get("announcement_date"), n.get("declared_per_share"), n.get("ex_date"), n.get("payment_date"))
        if key not in out: out[key] = n
        else: out[key].setdefault("alternate_sources", []).append(n["source_url"])
    return list(out.values())
