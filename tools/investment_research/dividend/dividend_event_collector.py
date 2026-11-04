"""Validate and deduplicate official dividend events. No scraping guesses."""
from __future__ import annotations
import json
from pathlib import Path
from tools.investment_research.dividend.evidence_registry import event_id, validate_source, validate_date

TYPES = {"DECLARED","EX_DATE","RECORD_DATE","PAYMENT_DATE","INCREASED","REDUCED","SUSPENDED","RESUMED"}


def normalize(rec: dict) -> dict:
    required = ("ticker","cik","event_type","announcement_date","source_url","source_type","evidence_sha256")
    for k in required:
        if not rec.get(k): raise ValueError(f"missing {k}")
    if rec["event_type"] not in TYPES: raise ValueError("bad event type")
    validate_source(rec["source_url"]); validate_date(rec["announcement_date"], "announcement_date")
    for k in ("ex_date","record_date","payment_date"):
        validate_date(rec.get(k), k)
    if rec.get("event_type") == "EX_DATE" and not rec.get("ex_date"):
        rec["ex_date_status"] = "EX_DATE_UNAVAILABLE"
    rec["event_id"] = rec.get("event_id") or event_id(
        ticker=rec["ticker"], event_type=rec["event_type"], event_date=rec["announcement_date"],
        source_url=rec["source_url"], evidence_sha256=rec["evidence_sha256"])
    rec["verification_status"] = rec.get("verification_status", "SOURCE_FETCHED")
    if rec["verification_status"] == "VERIFIED" and not rec.get("evidence_notes"):
        rec["verification_status"] = "PARTIALLY_VERIFIED"
    return rec


def dedupe(rows: list[dict]) -> list[dict]:
    out = {}
    for r in rows:
        n = normalize(r)
        # Same company/type/date/amount from a second source is one event.
        key = (n["ticker"].upper(), n["event_type"], n.get("announcement_date"),
               n.get("declared_per_share"), n.get("ex_date"), n.get("payment_date"))
        if key not in out:
            out[key] = n
        else:
            out[key].setdefault("alternate_sources", []).append(n["source_url"])
    return list(out.values())


def main():
    Path("data/research/dividend_events_p42.json").write_text("[]", encoding="utf-8")
    print("No official event records supplied; wrote empty event set.")


if __name__ == "__main__":
    main()
