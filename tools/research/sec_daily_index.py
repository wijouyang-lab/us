"""Parser for SEC's public EDGAR master index files (research-only).

The index identifies filings and filing dates, but does not prove intraday
publication time or historical first-seen availability. Callers must retain
actual retrieval timestamps and must not use filing_date as a release timestamp.
"""
from __future__ import annotations

from datetime import date
import re
from typing import Any

_RELEVANT_FORMS = {"8-K", "10-K", "10-Q"}
_MASTER_INDEX_ENTRY = re.compile(r"^(?P<cik>\d{1,10})/(?P<accession>\d{10}-\d{2}-\d{6})\.txt$", re.IGNORECASE)


def _date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must use YYYY-MM-DD") from exc


def _accession_from_compact(value: str) -> str | None:
    if len(value) != 18 or not value.isdigit():
        return None
    return f"{value[:10]}-{value[10:12]}-{value[12:]}"


def parse_sec_master_index(
    text: str,
    *,
    cik_tickers: dict[str, str],
    start_date: str,
    end_date: str,
    forms: set[str] | None = None,
) -> dict[str, Any]:
    """Parse pipe-delimited SEC master.idx text for a bounded explicit CIK universe."""
    start = _date(start_date, "start_date")
    end = _date(end_date, "end_date")
    if start > end:
        raise ValueError("start_date must not be after end_date")
    if not isinstance(text, str):
        raise ValueError("master index payload must be text")

    normalized_universe: dict[str, str] = {}
    for raw_cik, raw_ticker in cik_tickers.items():
        cik = str(raw_cik).strip()
        if not cik.isdigit() or len(cik) > 10:
            raise ValueError(f"invalid CIK in universe: {raw_cik!r}")
        ticker = str(raw_ticker or "").strip().upper().replace("$", "")
        if not ticker:
            raise ValueError(f"missing ticker for CIK {raw_cik!r}")
        normalized_universe[cik.lstrip("0") or "0"] = ticker

    accepted_forms = {str(form).strip().upper() for form in (forms or _RELEVANT_FORMS)}
    if not accepted_forms or any(not form for form in accepted_forms):
        raise ValueError("forms must contain at least one non-empty form")

    rows: dict[str, dict[str, Any]] = {}
    malformed_rows = 0
    duplicate_rows = 0
    data_started = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.lower().startswith("cik|company name|form type|date filed|filename"):
            data_started = True
            continue
        if not data_started:
            continue
        parts = line.split("|")
        if len(parts) != 5:
            malformed_rows += 1
            continue
        raw_cik, company_name, form, filed, filename = (part.strip() for part in parts)
        if not raw_cik.isdigit():
            malformed_rows += 1
            continue
        try:
            filed_date = date.fromisoformat(filed)
        except ValueError:
            malformed_rows += 1
            continue
        normalized_cik = raw_cik.lstrip("0") or "0"
        if normalized_cik not in normalized_universe:
            continue
        if form.upper() not in accepted_forms or not start <= filed_date <= end:
            continue
        path = filename.removeprefix("/")
        index_path = path.removeprefix("edgar/data/")
        match = _MASTER_INDEX_ENTRY.fullmatch(index_path)
        if not match:
            # Quarterly master.idx entries point at the complete submission text
            # (CIK/accession-with-dashes.txt), not the no-dash filing directory
            # used for individual HTML exhibits.
            malformed_rows += 1
            continue
        path_cik = match.group("cik").lstrip("0") or "0"
        accession = match.group("accession")
        accession_cik = accession.split("-", 1)[0].lstrip("0") or "0"
        if path_cik != normalized_cik or accession_cik != normalized_cik:
            malformed_rows += 1
            continue
        event_key = f"{normalized_cik}:{accession}"
        if event_key in rows:
            duplicate_rows += 1
            continue
        rows[event_key] = {
            "cik": raw_cik.zfill(10),
            "ticker": normalized_universe[normalized_cik],
            "company_name": company_name,
            "form": form.upper(),
            "filing_date": filed_date.isoformat(),
            "accession_number": accession,
            "filename": path,
            "source": "sec_edgar_master_index",
            "publication_timestamp_utc": None,
            "first_seen_at_utc": None,
            "availability_status": "index_metadata_only",
            "research_only": True,
        }

    events = sorted(rows.values(), key=lambda row: (row["filing_date"], row["ticker"], row["accession_number"]))
    return {
        "events": events,
        "metadata": {
            "source": "sec_edgar_master_index",
            "requested_start_date": start.isoformat(),
            "requested_end_date": end.isoformat(),
            "input_line_count": len(text.splitlines()),
            "event_count": len(events),
            "malformed_row_count": malformed_rows,
            "duplicate_count_removed": duplicate_rows,
            "timestamp_verified_count": 0,
            "historical_pit_eligible": False,
            "research_only": True,
            "limitations": [
                "Filing date is not an intraday publication timestamp.",
                "A downloaded historical index does not establish historical first-seen availability.",
                "Every event remains index_metadata_only until a separate timestamp source is verified.",
            ],
        },
    }
