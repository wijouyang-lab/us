"""Deterministic normalization for point-in-time research event records.

No network access, external dependencies, or production integration. Source adapters
should normalize source payloads through this module before feature generation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

ALLOWED_EVENT_TYPES = {
    "company_news", "earnings", "macro_release", "central_bank",
    "policy", "geopolitical", "other",
}


def _timestamp(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _stable_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_event(
    source: str,
    source_event_id: str,
    event_type: str,
    published_at_utc: str | None,
    first_seen_at_utc: str | None,
    *,
    headline: str | None = None,
    tickers: list[str] | None = None,
    sectors: list[str] | None = None,
    updated_at_utc: str | None = None,
    update_first_seen_at_utc: str | None = None,
    source_quality: str = "unknown",
    raw_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a stable, JSON-serializable event record with explicit missingness."""
    source_value = _stable_text(source).lower()
    source_id = _stable_text(source_event_id)
    kind = _stable_text(event_type).lower()
    if not source_value:
        raise ValueError("source is required")
    if not source_id:
        raise ValueError("source_event_id is required")
    if kind not in ALLOWED_EVENT_TYPES:
        kind = "other"

    published = _timestamp(published_at_utc)
    first_seen = _timestamp(first_seen_at_utc)
    updated = _timestamp(updated_at_utc)
    update_seen = _timestamp(update_first_seen_at_utc)
    normalized_tickers = sorted({_stable_text(t).upper().replace("$", "") for t in (tickers or []) if _stable_text(t)})
    normalized_sectors = sorted({_stable_text(s).lower() for s in (sectors or []) if _stable_text(s)})
    normalized_headline = _stable_text(headline)
    raw_json = json.dumps(raw_payload or {}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    content_hash = sha256(raw_json.encode("utf-8")).hexdigest()
    event_id = sha256(f"{source_value}|{source_id}".encode("utf-8")).hexdigest()

    if published is None or first_seen is None:
        availability = "timestamp_missing"
    elif not normalized_tickers and kind in {"company_news", "earnings"}:
        availability = "mapping_missing"
    else:
        availability = "available"

    return {
        "event_id": event_id,
        "source": source_value,
        "source_event_id": source_id,
        "event_type": kind,
        "published_at_utc": published,
        "first_seen_at_utc": first_seen,
        "updated_at_utc": updated,
        "update_first_seen_at_utc": update_seen,
        "headline": normalized_headline or None,
        "tickers": normalized_tickers,
        "sectors": normalized_sectors,
        "source_quality": _stable_text(source_quality).lower() or "unknown",
        "content_hash": content_hash,
        "availability_status": availability,
    }


def normalize_sec_filing(
    filing: Mapping[str, Any],
    *,
    first_seen_at_utc: str,
    ticker: str | None = None,
    source_quality: str = "official",
) -> dict[str, Any]:
    """Normalize SEC submissions-style filing metadata.

    filingDate and the SEC submissions JSON acceptanceDateTime field are not
    accepted as verified UTC publication times. Some records in that field have
    timezone/clock inconsistencies. Only an independently verified UTC timestamp
    in verifiedPublishedAtUtc is eligible; otherwise the timestamp stays missing.
    """
    accession = _stable_text(filing.get("accessionNumber"))
    form = _stable_text(filing.get("form")).upper()
    primary = _stable_text(filing.get("primaryDocument"))
    if not accession:
        raise ValueError("SEC filing accessionNumber is required")
    source_id = accession.replace("-", "")
    company = _stable_text(filing.get("companyName"))
    headline = " ".join(part for part in (form, company, primary) if part)
    published = filing.get("verifiedPublishedAtUtc")
    items = {
        part.strip() for part in _stable_text(filing.get("items")).split(",")
        if part.strip()
    }
    kind = (
        "earnings"
        if form in {"10-K", "10-Q"} or (form == "8-K" and "2.02" in items)
        else "company_news"
    )
    return normalize_event(
        source="sec_edgar",
        source_event_id=source_id,
        event_type=kind,
        published_at_utc=published,
        first_seen_at_utc=first_seen_at_utc,
        headline=headline,
        tickers=[ticker] if ticker else [],
        source_quality=source_quality,
        raw_payload={"form": form, "primaryDocument": primary, "accessionNumber": accession},
    )
