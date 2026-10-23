"""Deterministic parser for SEC submissions JSON recent-filings payloads.

This module consumes caller-supplied payloads only: no network requests and no
production scanner integration. It deliberately does not infer an exact public
timestamp from filingDate.
"""
from __future__ import annotations

from typing import Any, Mapping

from tools.research.pit_event_records import normalize_sec_filing


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
) -> list[dict[str, Any]]:
    """Parse SEC submissions JSON and normalize recent filing records.

    Expected shape is the SEC company-submissions response containing a
    filings.recent object with parallel arrays. The first-seen timestamp must
    be supplied by the collector, not copied from the source payload.
    """
    filings = payload.get("filings")
    if not isinstance(filings, Mapping):
        return []
    recent = filings.get("recent")
    rows = _rows_from_columnar_recent(recent if isinstance(recent, Mapping) else {})
    company_name = str(payload.get("name") or "").strip()
    records: list[dict[str, Any]] = []
    for row in rows:
        form = str(row.get("form") or "").strip().upper()
        items = str(row.get("items") or "")
        normalized = dict(row)
        normalized["companyName"] = company_name
        normalized["acceptanceDateTimeUtc"] = row.get("acceptanceDateTime")
        record = normalize_sec_filing(
            normalized,
            first_seen_at_utc=first_seen_at_utc,
            ticker=ticker,
            source_quality=source_quality,
        )
        record["event_type"] = _event_type_for_filing(form, items)
        records.append(record)
    return records
