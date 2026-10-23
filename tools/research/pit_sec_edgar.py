"""Deterministic parsers for point-in-time SEC submission metadata.

This module consumes caller-supplied payloads only: no network requests and no
production scanner integration. It never treats the raw submissions JSON
acceptanceDateTime field as verified UTC. A separately supplied official SGML
submission header can be parsed using the SEC-documented fixed EST offset
(UTC-05:00) and converted to UTC. This timestamp is not first-public-availability time.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any, Mapping

from tools.research.pit_event_records import normalize_sec_filing


_SEC_ACCEPTANCE_TZ = timezone(timedelta(hours=-5), name="EST")
_ACCEPTANCE_PATTERN = re.compile(
    r"<ACCEPTANCE-DATETIME>\s*(\d{14})\b",
    re.IGNORECASE,
)
_ACCESSION_PATTERN = re.compile(
    r"(?:<ACCESSION-NUMBER>\s*|ACCESSION\s+NUMBER\s*:\s*)([0-9-]{18,})",
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


def parse_sec_acceptance_datetime(
    submission_text: str | None,
    *,
    expected_accession: str | None = None,
) -> dict[str, str | None]:
    """Parse a single ACCEPTANCE-DATETIME from an official SEC SGML submission.

    The SEC documents Acceptance Time as EST, so this conversion uses fixed
    UTC-05:00 rather than applying seasonal daylight-saving offsets. This is an
    EDGAR acceptance timestamp, not a claim about when content first became
    available on SEC.gov. Malformed or multiple timestamps fail closed.
    """
    if not isinstance(submission_text, str) or not submission_text.strip():
        return {"published_at_utc": None, "status": "header_missing"}
    if expected_accession:
        accession_matches = _ACCESSION_PATTERN.findall(submission_text)
        if len(accession_matches) != 1:
            return {"published_at_utc": None, "status": "accession_missing_or_ambiguous"}
        expected = re.sub(r"\D", "", expected_accession)
        observed = re.sub(r"\D", "", accession_matches[0])
        if not expected or observed != expected:
            return {"published_at_utc": None, "status": "accession_mismatch"}

    matches = _ACCEPTANCE_PATTERN.findall(submission_text)
    if not matches:
        return {"published_at_utc": None, "status": "acceptance_datetime_missing"}
    if len(matches) != 1:
        return {"published_at_utc": None, "status": "acceptance_datetime_ambiguous"}

    try:
        local_naive = datetime.strptime(matches[0], "%Y%m%d%H%M%S")
    except ValueError:
        return {"published_at_utc": None, "status": "acceptance_datetime_invalid"}

    est_value = local_naive.replace(tzinfo=_SEC_ACCEPTANCE_TZ)
    utc_value = est_value.astimezone(timezone.utc)

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
    header's ACCEPTANCE-DATETIME from the SEC-documented fixed EST offset
    (UTC-05:00) to UTC.
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
        timestamp_result = parse_sec_acceptance_datetime(
            header_text,
            expected_accession=accession,
        )
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
