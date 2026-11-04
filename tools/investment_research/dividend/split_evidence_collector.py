"""Collect SEC XBRL split-conversion facts. They are partial evidence, never
SPLIT_CONFIRMED without an official effective date and announcement."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from datetime import datetime, timezone
from tools.investment_research.dividend.evidence_registry import split_id

TAG = "StockholdersEquityNoteStockSplitConversionRatio1"


def collect(ticker: str, cik: str, companyfacts: dict) -> dict:
    rows = (((companyfacts.get("facts") or {}).get("us-gaap") or {}).get(TAG) or {}).get("units", {}).get("pure", [])
    events = []
    for r in rows:
        raw = json.dumps({k: r.get(k) for k in ("end", "val", "accn", "form", "filed")}, sort_keys=True).encode()
        h = hashlib.sha256(raw).hexdigest()
        src = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        events.append({
            "event_id": split_id(ticker=ticker, effective_date=r.get("end"), ratio=r.get("val"),
                                 source_url=src, evidence_sha256=h),
            "ticker": ticker, "cik": cik, "split_ratio": r.get("val"),
            "ratio_convention": "new_shares_per_old_share",
            "announcement_date": None, "effective_date": None,
            "fact_period_end": r.get("end"),
            "source_url": src, "source_type": "SEC CompanyFacts XBRL",
            "accession_number": r.get("accn"), "form": r.get("form"),
            "filed": r.get("filed"), "evidence_sha256": h,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "verification_status": "PARTIALLY_VERIFIED",
            "evidence_notes": "ratio is SEC XBRL; effective/announcement dates require filing/IR evidence",
        })
    # Deduplicate repeated facts from multiple filings by ratio+fact end; keep latest accession.
    dedup = {}
    for e in events:
        key = (e["split_ratio"], e["fact_period_end"])
        if key not in dedup or (e.get("filed") or "") > (dedup[key].get("filed") or ""):
            dedup[key] = e
    events = sorted(dedup.values(), key=lambda x: (x.get("fact_period_end") or "", x.get("filed") or ""))
    status = "PARTIALLY_VERIFIED" if events else "SPLIT_HISTORY_INCOMPLETE"
    return {"ticker": ticker, "cik": cik, "status": status,
            "source_share_basis": "UNKNOWN", "events": events}


def main():
    snap = json.loads(Path("docs/research/sec_fundamentals_snapshot.json").read_text())
    out = []
    for t, a in snap.items():
        cik = a.get("cik"); p = Path(f"data/sec/cache/companyfacts_{cik}.json")
        if not p.exists():
            out.append({"ticker": t, "cik": cik, "status": "SPLIT_HISTORY_INCOMPLETE", "events": []}); continue
        out.append(collect(t, cik, json.loads(p.read_text())))
    Path("data/research/split_evidence_p42.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("splits", sum(len(x["events"]) for x in out), "tickers", len(out))


if __name__ == "__main__":
    main()
