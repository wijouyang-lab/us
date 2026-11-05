"""Normalize US dividend events into a security-level research schema (P6.11).

No vendor endpoint is available in the pinned AkShare version; this module is
still the canonical normalizer and is tested with local fixtures.
"""
from __future__ import annotations
import csv, hashlib, json
from pathlib import Path
from datetime import date

FIELDS = ["ticker","cik","security_type","issuer_name","source","source_symbol",
          "announcement_date","ex_dividend_date","record_date","payment_date","dps",
          "currency","dividend_type","frequency","fiscal_period","source_url",
          "retrieved_at","raw_payload_hash","verification_status","blocker_codes"]
EVENT_TYPES = {"REGULAR_CASH","SPECIAL_CASH","ADR_DISTRIBUTION","STOCK_DIVIDEND",
               "RETURN_OF_CAPITAL","OTHER","UNKNOWN"}


def _date(v):
    if not v: return ""
    try: return date.fromisoformat(str(v)[:10]).isoformat()
    except ValueError: return ""


def normalize_event(raw: dict, ticker: str, cik: str, security_type: str,
                    issuer_name: str, source: str, source_symbol: str,
                    retrieved_at: str, adr_ratio_verified: bool = False) -> dict:
    dps = raw.get("dps")
    currency = raw.get("currency") or ""
    dtype = (raw.get("dividend_type") or "UNKNOWN").upper()
    if dtype not in EVENT_TYPES: dtype = "UNKNOWN"
    blockers = []
    if security_type == "ADR" and not adr_ratio_verified:
        blockers.append("ADR_RATIO_UNVERIFIED")
    if not currency:
        blockers.append("CURRENCY_MISSING")
    if not raw.get("ex_dividend_date"):
        blockers.append("EX_DATE_MISSING")
    if not raw.get("payment_date"):
        blockers.append("PAYMENT_DATE_MISSING")
    payload = json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {"ticker": ticker, "cik": cik, "security_type": security_type,
            "issuer_name": issuer_name, "source": source, "source_symbol": source_symbol,
            "announcement_date": _date(raw.get("announcement_date")),
            "ex_dividend_date": _date(raw.get("ex_dividend_date")),
            "record_date": _date(raw.get("record_date")),
            "payment_date": _date(raw.get("payment_date")),
            "dps": dps if dps is not None else "", "currency": currency,
            "dividend_type": dtype, "frequency": raw.get("frequency") or "",
            "fiscal_period": raw.get("fiscal_period") or "",
            "source_url": raw.get("source_url") or "", "retrieved_at": retrieved_at,
            "raw_payload_hash": hashlib.sha256(payload.encode()).hexdigest(),
            "verification_status": "DIVIDEND_EVENT_FIELDS_COMPLETE" if not blockers else "DIVIDEND_PARTIAL_DATA",
            "blocker_codes": "|".join(blockers)}


def write_events(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)


def dedupe_events(rows):
    seen = set(); out = []; duplicates = 0
    for r in rows:
        key = (r.get("ticker"), r.get("ex_dividend_date"), r.get("dps"),
               r.get("currency"), r.get("dividend_type"))
        if key in seen:
            duplicates += 1; continue
        seen.add(key); out.append(r)
    return out, duplicates
