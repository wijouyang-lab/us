"""Deterministic parsers for point-in-time SEC submission metadata.

This module consumes caller-supplied payloads only: no network requests and no
production scanner integration. It never treats the raw submissions JSON
acceptanceDateTime field as verified UTC. A separately supplied official SGML
submission header can be parsed as America/New_York local time and converted to
UTC, with DST ambiguity/nonexistence rejected.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from tools.research.pit_event_records import normalize_sec_filing


_NEW_YORK = ZoneInfo("America/New_York")
_ACCEPTANCE_PATTERN = re.compile(
    r"<ACCEPTANCE-DATETIME>\s*(\d{14})\b",
    re.IGNORECASE,
)


def _rows_from_columnar_recent(recent: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Convert SEC's columnar recent-filings arrays into row dictionaries."""
    if not isinstance(recent, Mapping):
        return []
    columns = {key: value for key, value in recent.items() if isinstance(value, list)}
    if not columns:
        return []
    row_count = max((len(values) for values in columns.values()), default=0)
    rows: list[dict[str, Any]] = []
    for index in range(row_count):
        row = {
            key: values[index]
            for key, values in columns.items()
            if index < len(values)
        }
        if row.get("accessionNumber"):
            rows.append(row)
    return rows


def parse_sec_acceptance_datetime(submission_text: str | None) -> dict[str, str | None]:
    """Parse a single ACCEPTANCE-DATETIME from an official SEC SGML submission.

    The header timestamp is interpreted as America/New_York local wall time.
    Returns a normalized UTC timestamp only if exactly one valid, unambiguous
    local timestamp is found; all other cases fail closed with a status.
    """
    if not isinstance(submission_text, str) or not submission_text.strip():
        return {"published_at_utc": None, "status": "header_missing"}
    matches = _ACCEPTANCE_PATTERN.findall(submission_text)
    if not matches:
        return {"published_at_utc": None, "status": "acceptance_datetime_missing"}
    if len(matches) != 1:
        return {"published_at_utc": None, "status": "acceptance_datetime_ambiguous"}

    try:
        local_naive = datetime.strptime(matches[0], "%Y%m%d%H%M%S")
    except ValueError:
        return {"published_at_utc": None, "status": "acceptance_datetime_invalid"}

    local_fold0 = local_naive.replace(tzinfo=_NEW_YORK, fold=0)
    local_fold1 = local_naive.replace(tzinfo=_NEW_YORK, fold=1)
    if local_fold0.utcoffset() != local_fold1.utcoffset():
        return {"published_at_utc": None, "status": "acceptance_datetime_dst_ambiguous"}

    utc_value = local_fold0.astimezone(timezone.utc)
    round_trip = utc_value.astimezone(_NEW_YORK).replace(tzinfo=None)
    if round_trip != local_naive:
        return {"published_at_utc": None, "status": "acceptance_datetime_dst_nonexistent"}

    return {
        "published_at_utc": utc_value.isoformat().replace("+00:00", "Z"),
        "status": "verified_from_sgml_header",
    }


def _event_type_for_filing(form: str, items: str) -> str:
    normalized_form = form.strip().upper()
    normalized_items = {part.strip() for part in items.split(",") if part.strip()}
    if normalized_form in {"10-K", "10-Q"}:
        return "earnings"
    if normalized_form == "8-K" and "2.02" in normalized_items:
        return "earnings"
    return "company_news"


def parse_sec_submissions(
    payload: Mapping[str, Any],
    *,
    first_seen_at_utc: str,
    ticker: str | None = None,
    source_quality: str = "official",
    submission_headers_by_accession: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Parse SEC submissions JSON plus optional SGML headers indexed by accession.

    Expected payload is the SEC company-submissions response containing
    filings.recent parallel arrays. The collector must supply first-seen time.
    The raw acceptanceDateTime and filingDate arrays are never used as verified
    UTC timestamps. To enable a filing timestamp, supply its official SGML header
    keyed by accession number (with or without dashes); the parser converts the
    header's ACCEPTANCE-DATETIME from America/New_York to UTC.
    """
    filings = payload.get("filings")
    if not isinstance(filings, Mapping):
        return []
    recent = filings.get("recent")
    rows = _rows_from_columnar_recent(recent if isinstance(recent, Mapping) else {})
    company_name = str(payload.get("name") or "").strip()
    headers = submission_headers_by_accession or {}
    records: list[dict[str, Any]] = []
    for row in rows:
        accession = str(row.get("accessionNumber") or "").strip()
        normalized_accession = accession.replace("-", "")
        form = str(row.get("form") or "").strip().upper()
        items = str(row.get("items") or "")

        header_text = headers.get(normalized_accession) or headers.get(accession)
        timestamp_result = parse_sec_acceptance_datetime(header_text)
        normalized = dict(row)
        normalized["companyName"] = company_name
        normalized["verifiedPublishedAtUtc"] = timestamp_result["published_at_utc"]

        record = normalize_sec_filing(
            normalized,
            first_seen_at_utc=first_seen_at_utc,
            ticker=ticker,
            source_quality=source_quality,
        )
        record["event_type"] = _event_type_for_filing(form, items)
        record["publication_timestamp_source"] = (
            "sec_sgml_acceptance_datetime"
            if timestamp_result["status"] == "verified_from_sgml_header"
            else None
        )
        record["publication_timestamp_status"] = timestamp_result["status"]
        records.append(record)
    return records
