"""Normalize SmarterDividends, Yahoo and Nasdaq dividend responses (P6.12)."""
from __future__ import annotations
import hashlib, json
from datetime import date

FIELDS = ["ticker","cik","security_type","source","source_symbol","announcement_date",
          "ex_dividend_date","record_date","payment_date","dps","currency","dividend_type",
          "frequency","source_url","as_of","retrieved_at","raw_payload_hash","verification_status",
          "blocker_codes","provider_event_kind","split_adjustment"]
EVENT_TYPES = {"REGULAR_CASH","SPECIAL_CASH","ADR_DISTRIBUTION","STOCK_DIVIDEND",
               "RETURN_OF_CAPITAL","OTHER","UNKNOWN"}


def _d(v):
    if not v: return ""
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try: return date.fromisoformat(s[:10]).isoformat() if fmt == "%Y-%m-%d" else __import__("datetime").datetime.strptime(s[:10], fmt).date().isoformat()
        except ValueError: pass
    return ""


def standard_event(*, ticker, cik, security_type, source, source_symbol,
                   announcement_date="", ex_dividend_date="", record_date="",
                   payment_date="", dps="", currency="", dividend_type="UNKNOWN",
                   frequency="", source_url="", as_of="", retrieved_at="",
                   raw_payload=None, provider_event_kind="", split_adjustment="",
                   adr_ratio_verified=False) -> dict:
    dtype = (dividend_type or "UNKNOWN").upper()
    if dtype not in EVENT_TYPES: dtype = "UNKNOWN"
    blockers = []
    if security_type == "ADR" and not adr_ratio_verified: blockers.append("ADR_RATIO_UNVERIFIED")
    if not currency: blockers.append("CURRENCY_MISSING")
    if not ex_dividend_date: blockers.append("EX_DATE_MISSING")
    if not payment_date: blockers.append("PAYMENT_DATE_MISSING")
    if not announcement_date: blockers.append("DECLARATION_DATE_MISSING")
    if not record_date: blockers.append("RECORD_DATE_MISSING")
    payload = json.dumps(raw_payload or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {"ticker": ticker, "cik": cik, "security_type": security_type, "source": source,
            "source_symbol": source_symbol, "announcement_date": _d(announcement_date),
            "ex_dividend_date": _d(ex_dividend_date), "record_date": _d(record_date),
            "payment_date": _d(payment_date), "dps": dps if dps is not None else "",
            "currency": currency or "", "dividend_type": dtype, "frequency": frequency or "",
            "source_url": source_url or "", "as_of": as_of or "", "retrieved_at": retrieved_at or "",
            "raw_payload_hash": hashlib.sha256(payload.encode()).hexdigest(),
            "verification_status": "FULL_EVENT_FIELDS" if not blockers else "PARTIAL_EVENT",
            "blocker_codes": "|".join(blockers), "provider_event_kind": provider_event_kind,
            "split_adjustment": split_adjustment}


def stop_after_status(status):
    return status == 429
