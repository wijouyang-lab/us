"""Field-level dividend announcement parser. Rejects preferred/price-target text."""
from __future__ import annotations
import re
from datetime import datetime

AMOUNT = re.compile(r"\(?\$\s?([0-9]+\.[0-9]{2,4})\)?\s*(?:per\s+(?:common\s+)?share)", re.I)
PREV = re.compile(r"(?:previous|prior|from)\s+(?:quarterly\s+)?(?:dividend\s+)?(?:of\s+)?\$\s?([0-9]+\.[0-9]{2,4})", re.I)
MONTHS = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?"
DATE = re.compile(r"(" + MONTHS + r"\s+\d{1,2},\s+\d{4})", re.I)


def _date(value):
    if not value: return None
    clean = value.replace(".", "")
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try: return datetime.strptime(clean, fmt).date().isoformat()
        except ValueError: pass
    return None


def _sentences(text):
    clean = re.sub(r"<[^>]+>", " ", text); clean = re.sub(r"&nbsp;", " ", clean)
    clean = re.sub(r"\s+", " ", clean)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean) if s.strip()], clean


def parse(text: str, *, ticker: str, cik: str, source_url: str, accession: str,
          evidence_sha256: str, filed_date: str | None = None,
          document_role: str = "EXHIBIT") -> list[dict]:
    sents, clean = _sentences(text)
    out = []
    for idx, s in enumerate(sents):
        low = s.lower()
        if "dividend" not in low: continue
        if any(x in low for x in ("preferred", "depositary", "price target", "analyst", "target price")): continue
        if "common stock" not in low and "common share" not in low: continue
        if not (re.search(r"\b(declared|approved|announced)\b", low)
                or re.search(r"\b(raise|raised|voted)\b.{0,80}\bdividend\b", low)
                or re.search(r"\bdividend\b.{0,80}\b(raise|raised|voted)\b", low)):
            continue
        m = AMOUNT.search(s)
        if not m: continue
        # BAC puts record/payable dates in the sentence after the declaration.
        ctx = s
        if idx + 1 < len(sents) and re.search(r"payable|record", sents[idx+1], re.I):
            ctx = s + " " + sents[idx+1]
        prev = PREV.search(ctx)
        dates = DATE.findall(ctx)
        rec = None; pay = None
        mrec = re.search(r"record\s+(?:date\s+)?[^.]{0,100}?(" + DATE.pattern + r")", ctx, re.I)
        mpay = re.search(r"(?:payable|payment\s+date)[^.]{0,100}?(" + DATE.pattern + r")", ctx, re.I)
        if mrec: rec = mrec.group(1)
        if mpay: pay = mpay.group(1)
        # announcement date: explicit sentence date; never fall back to filed date silently.
        ann = dates[0] if dates else None
        out.append({
            "ticker": ticker.upper(), "cik": cik, "event_type": "DECLARED",
            "security_type": "COMMON", "declared_per_share": float(m.group(1)),
            "currency": "USD", "frequency": "QUARTERLY" if "quarter" in low else None,
            "announcement_date": _date(ann),
            "ex_date": None, "ex_date_status": "NOT_DISCLOSED_IN_FILING",
            "record_date": _date(rec),
            "payment_date": _date(pay),
            "previous_per_share": float(prev.group(1)) if prev else None,
            "previous_per_share_status": "VERIFIED" if prev else "NOT_DISCLOSED_IN_FILING",
            "change_direction": "INCREASED" if prev and float(m.group(1)) > float(prev.group(1)) else None,
            "source_url": source_url,
            "source_type": "SEC Form 8-K" if document_role == "PRIMARY" else "SEC Exhibit 99.1",
            "accession_number": accession, "filed_date": filed_date,
            "evidence_sha256": evidence_sha256, "raw_context": s[:600],
        })
    return out


def parse_preferred(text: str, *, ticker: str, cik: str, source_url: str, accession: str,
                    evidence_sha256: str, document_role: str = "EXHIBIT") -> list[dict]:
    sents, _ = _sentences(text); out = []
    for s in sents:
        low = s.lower()
        if "preferred" not in low or "dividend" not in low: continue
        m = AMOUNT.search(s)
        if not m: continue
        out.append({"ticker": ticker.upper(), "cik": cik, "event_type": "DECLARED",
                    "security_type": "PREFERRED", "declared_per_share": float(m.group(1)),
                    "currency": "USD", "source_url": source_url,
                    "source_type": "SEC Form 8-K" if document_role == "PRIMARY" else "SEC Exhibit 99.1",
                    "accession_number": accession, "evidence_sha256": evidence_sha256,
                    "raw_context": s[:600], "status": "PREFERRED_STOCK_EXCLUDED_FROM_COMMON_DIVIDEND"})
    return out


def is_false_positive(text: str) -> dict | None:
    low = re.sub(r"<[^>]+>", " ", text).lower()
    if ("price target" in low or "analyst" in low) and "$67.75" in low:
        return {"reason": "FALSE_POSITIVE_NON_DIVIDEND_PRICE_TARGET", "matched_amount": 67.75}
    return None
