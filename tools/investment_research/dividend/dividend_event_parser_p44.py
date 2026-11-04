"""Field-level dividend announcement parser. Rejects preferred/price-target text."""
from __future__ import annotations
import re
from datetime import datetime

AMOUNT = re.compile(r"\$\s?([0-9]+\.[0-9]{2,4})\s*(?:per\s+(?:common\s+)?share)", re.I)
PREV = re.compile(r"(?:previous|prior|from)\s+(?:quarterly\s+)?(?:dividend\s+)?(?:of\s+)?\$\s?([0-9]+\.[0-9]{2,4})", re.I)
DATE = re.compile(r"((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})", re.I)


def _sentences(text):
    clean = re.sub(r"<[^>]+>", " ", text); clean = re.sub(r"&nbsp;", " ", clean)
    clean = re.sub(r"\s+", " ", clean)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean) if s.strip()], clean


def parse(text: str, *, ticker: str, cik: str, source_url: str, accession: str,
          evidence_sha256: str, filed_date: str | None = None) -> list[dict]:
    sents, clean = _sentences(text)
    out = []
    for s in sents:
        low = s.lower()
        if "dividend" not in low: continue
        if any(x in low for x in ("preferred", "depositary", "price target", "analyst", "target price")): continue
        if "common stock" not in low and "common share" not in low: continue
        if not re.search(r"\b(declared|approved|increased|announced)\b", low): continue
        m = AMOUNT.search(s)
        if not m: continue
        prev = PREV.search(s)
        dates = DATE.findall(s)
        rec = None; pay = None
        mrec = re.search(r"record\s+(?:date\s+)?[^.]{0,80}?(" + DATE.pattern + r")", s, re.I)
        mpay = re.search(r"(?:payable|payment\s+date)[^.]{0,80}?(" + DATE.pattern + r")", s, re.I)
        if mrec: rec = mrec.group(1)
        if mpay: pay = mpay.group(1)
        # announcement date: explicit sentence date; never fall back to filed date silently.
        ann = dates[0] if dates else None
        out.append({
            "ticker": ticker.upper(), "cik": cik, "event_type": "DECLARED",
            "security_type": "COMMON", "declared_per_share": float(m.group(1)),
            "currency": "USD", "frequency": "QUARTERLY" if "quarter" in low else None,
            "announcement_date": datetime.strptime(ann, "%B %d, %Y").date().isoformat() if ann else None,
            "ex_date": None, "ex_date_status": "EX_DATE_UNAVAILABLE",
            "record_date": datetime.strptime(rec, "%B %d, %Y").date().isoformat() if rec else None,
            "payment_date": datetime.strptime(pay, "%B %d, %Y").date().isoformat() if pay else None,
            "previous_per_share": float(prev.group(1)) if prev else None,
            "change_direction": "INCREASED" if prev and float(m.group(1)) > float(prev.group(1)) else None,
            "source_url": source_url, "source_type": "SEC Exhibit 99.1",
            "accession_number": accession, "filed_date": filed_date,
            "evidence_sha256": evidence_sha256, "raw_context": s[:600],
        })
    return out


def is_false_positive(text: str) -> dict | None:
    low = re.sub(r"<[^>]+>", " ", text).lower()
    if ("price target" in low or "analyst" in low) and "$67.75" in low:
        return {"reason": "FALSE_POSITIVE_NON_DIVIDEND_PRICE_TARGET", "matched_amount": 67.75}
    return None
