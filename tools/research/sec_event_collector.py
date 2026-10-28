"""Free official SEC filing snapshot collector for research/paper observation.

This is deliberately separate from the production scanner. It uses the public SEC
submissions and Archives endpoints, requires an identifiable User-Agent contact,
paces requests, and emits point-in-time event JSON plus coverage metadata.

Important: a current backfill records when this collector first saw each header;
it cannot reconstruct when a historical system first saw it. Under strict
first-seen eligibility, these records are for forward observation from collection
time, not proof of a no-lookahead historical backtest.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from tools.research.pit_sec_edgar import parse_sec_submissions

_ALLOWED_HOSTS = {"data.sec.gov", "www.sec.gov"}
_RETRYABLE_CODES = {429, 500, 502, 503, 504}
_RELEVANT_FORMS = {"8-K", "10-K", "10-Q"}


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("collector clock must return a timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_cik(value: Any) -> str:
    """Return a 10-digit CIK, rejecting ambiguous non-digit identifiers."""
    raw = str(value or "").strip()
    if not raw.isdigit() or len(raw) > 10:
        raise ValueError(f"invalid CIK: {value!r}")
    return raw.zfill(10)


def _as_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must use YYYY-MM-DD") from exc


def load_universe(path: str | Path) -> list[dict[str, str]]:
    """Load explicit CIK/ticker pairs; do not infer historical ticker mappings."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read universe file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid universe JSON: {exc}") from exc
    if not isinstance(payload, list) or not payload:
        raise ValueError("universe JSON must be a non-empty array of CIK/ticker objects")

    result: list[dict[str, str]] = []
    seen_ciks: set[str] = set()
    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            raise ValueError(f"universe row {index} must be an object")
        cik = normalize_cik(row.get("cik"))
        ticker = str(row.get("ticker") or "").strip().upper().replace("$", "")
        if not ticker:
            raise ValueError(f"universe row {index} is missing ticker")
        if cik in seen_ciks:
            raise ValueError(f"duplicate CIK in universe: {cik}")
        seen_ciks.add(cik)
        result.append({"cik": cik, "ticker": ticker})
    return result


def _rows_from_recent(recent: Mapping[str, Any]) -> list[dict[str, Any]]:
    columns = {key: value for key, value in recent.items() if isinstance(value, list)}
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


def _one_filing_payload(name: Any, recent: Mapping[str, Any], row: Mapping[str, Any]) -> dict[str, Any]:
    one_recent = {
        key: [row.get(key)]
        for key, values in recent.items()
        if isinstance(values, list)
    }
    return {"name": name, "filings": {"recent": one_recent}}


class SecEventCollector:
    """Rate-limited client for a small, explicit SEC CIK research universe."""

    def __init__(
        self,
        user_agent: str,
        *,
        timeout_seconds: float = 20.0,
        min_request_interval_seconds: float = 0.15,
        max_retries: int = 3,
        opener: Callable[..., Any] | None = None,
        sleep: Callable[[float], None] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(user_agent, str) or "@" not in user_agent or not user_agent.strip():
            raise ValueError("User-Agent must identify the research application and a contact email")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if min_request_interval_seconds < 0.1:
            raise ValueError("request interval must be at least 0.1 seconds")
        if max_retries < 0 or max_retries > 5:
            raise ValueError("max_retries must be between 0 and 5")
        self.user_agent = user_agent.strip()
        self.timeout_seconds = timeout_seconds
        self.min_request_interval_seconds = min_request_interval_seconds
        self.max_retries = max_retries
        self.opener = opener or urlopen
        self.sleep = sleep or time.sleep
        self.now = now or (lambda: datetime.now(timezone.utc))
        self._has_requested = False

    def _retry_delay(self, error: HTTPError | None, attempt: int) -> float:
        if error is not None and error.headers is not None:
            retry_after = error.headers.get("Retry-After")
            if retry_after:
                try:
                    return min(30.0, max(0.0, float(retry_after)))
                except ValueError:
                    pass
        return float(min(2 ** attempt, 8))

    def _request_text(self, url: str) -> str:
        host = urlparse(url).hostname
        if host not in _ALLOWED_HOSTS or not url.startswith("https://"):
            raise ValueError("SEC collector only permits HTTPS requests to data.sec.gov and www.sec.gov")

        for attempt in range(self.max_retries + 1):
            if self._has_requested:
                self.sleep(self.min_request_interval_seconds)
            request = Request(
                url,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
                    "Accept-Encoding": "identity",
                },
            )
            self._has_requested = True
            try:
                with self.opener(request, timeout=self.timeout_seconds) as response:
                    status = int(getattr(response, "status", 200))
                    if status in _RETRYABLE_CODES and attempt < self.max_retries:
                        self.sleep(float(min(2 ** attempt, 8)))
                        continue
                    if status < 200 or status >= 300:
                        raise RuntimeError(f"SEC request returned HTTP {status}: {url}")
                    raw = response.read()
                    headers = getattr(response, "headers", {})
                    charset_getter = getattr(headers, "get_content_charset", None)
                    charset = charset_getter() if callable(charset_getter) else None
                    return raw.decode(charset or "utf-8", errors="replace")
            except HTTPError as exc:
                if exc.code in _RETRYABLE_CODES and attempt < self.max_retries:
                    self.sleep(self._retry_delay(exc, attempt))
                    continue
                raise RuntimeError(f"SEC request failed with HTTP {exc.code}: {url}") from exc
            except URLError as exc:
                if attempt < self.max_retries:
                    self.sleep(self._retry_delay(None, attempt))
                    continue
                raise RuntimeError(f"SEC request failed: {url}: {exc}") from exc
        raise RuntimeError(f"SEC request exhausted retries: {url}")

    def _request_json(self, url: str) -> dict[str, Any]:
        try:
            result = json.loads(self._request_text(url))
        except json.JSONDecodeError as exc:
            raise ValueError(f"SEC returned invalid JSON for {url}") from exc
        if not isinstance(result, dict):
            raise ValueError(f"SEC JSON response must be an object: {url}")
        return result

    def collect_company(
        self,
        cik: str,
        ticker: str,
        *,
        start_date: str,
        end_date: str,
        max_filings: int = 25,
    ) -> dict[str, Any]:
        """Fetch relevant recent filings and verify timestamps from SEC index headers."""
        cik10 = normalize_cik(cik)
        cik_numeric = str(int(cik10))
        ticker_value = str(ticker or "").strip().upper().replace("$", "")
        if not ticker_value:
            raise ValueError("ticker is required")
        start = _as_date(start_date, "start_date")
        end = _as_date(end_date, "end_date")
        if start > end:
            raise ValueError("start_date must not be after end_date")
        if isinstance(max_filings, bool) or max_filings < 1 or max_filings > 500:
            raise ValueError("max_filings must be between 1 and 500")

        collection_started = _utc_iso(self.now())
        submissions_url = f"https://data.sec.gov/submissions/CIK{cik10}.json"
        submissions = self._request_json(submissions_url)
        filings_obj = submissions.get("filings")
        if not isinstance(filings_obj, Mapping):
            raise ValueError("SEC submissions JSON has no filings object")
        recent = filings_obj.get("recent")
        if not isinstance(recent, Mapping):
            raise ValueError("SEC submissions JSON has no filings.recent object")
        rows = _rows_from_recent(recent)

        recent_dates = [
            filing_date
            for row in rows
            if (filing_date := _safe_filing_date(row.get("filingDate"))) is not None
        ]
        history_may_be_incomplete = not recent_dates or min(recent_dates) > start
        candidates: list[tuple[date, dict[str, Any]]] = []
        for row in rows:
            form = str(row.get("form") or "").strip().upper()
            filing_date = _safe_filing_date(row.get("filingDate"))
            if filing_date is None or form not in _RELEVANT_FORMS:
                continue
            if start <= filing_date <= end:
                candidates.append((filing_date, row))
        candidates.sort(key=lambda pair: (pair[0], str(pair[1].get("accessionNumber") or "")))
        truncated_by_limit = len(candidates) > max_filings
        selected = candidates[-max_filings:] if truncated_by_limit else candidates

        events: list[dict[str, Any]] = []
        header_fetch_errors = 0
        header_fetch_error_types: dict[str, int] = {}
        header_http_status_counts: dict[str, int] = {}
        for _, row in selected:
            accession = str(row.get("accessionNumber") or "").strip()
            accession_compact = accession.replace("-", "")
            header_url = (
                f"https://www.sec.gov/Archives/edgar/data/{cik_numeric}/"
                f"{accession_compact}/{accession}-index-headers.html"
            )
            filing_payload = _one_filing_payload(submissions.get("name"), recent, row)
            try:
                header_text = self._request_text(header_url)
                first_seen_at_utc = _utc_iso(self.now())
                records = parse_sec_submissions(
                    filing_payload,
                    first_seen_at_utc=first_seen_at_utc,
                    ticker=ticker_value,
                    submission_headers_by_accession={accession_compact: header_text},
                )
                if not records:
                    raise ValueError("SEC filing row could not be normalized")
                event = records[0]
                event["source_header_sha256"] = sha256(header_text.encode("utf-8")).hexdigest()
            except Exception as exc:
                header_fetch_errors += 1
                error_type = type(exc).__name__
                header_fetch_error_types[error_type] = header_fetch_error_types.get(error_type, 0) + 1
                # Preserve status for auditing; do not retry access-denied responses.
                status_match = re.search(r"HTTP (\d{3})", str(exc))
                if status_match:
                    status_key = status_match.group(1)
                    header_http_status_counts[status_key] = header_http_status_counts.get(status_key, 0) + 1
                first_seen_at_utc = _utc_iso(self.now())
                records = parse_sec_submissions(
                    filing_payload,
                    first_seen_at_utc=first_seen_at_utc,
                    ticker=ticker_value,
                )
                event = records[0]
                event["availability_status"] = "fetch_error"
                event["publication_timestamp_status"] = "fetch_error"
                event["fetch_error_type"] = error_type
                event["fetch_error_detail"] = str(exc)[:300]
                if status_match:
                    event["fetch_http_status"] = int(status_match.group(1))
            event["source_url"] = header_url
            event["collector_source"] = "sec_edgar_public_archives"
            event["sec_filing_date"] = str(row.get("filingDate") or "")
            events.append(event)

        events.sort(
            key=lambda row: (
                str(row.get("published_at_utc") or ""),
                str(row.get("tickers", [""])[0] if row.get("tickers") else ""),
                str(row.get("event_id") or ""),
            )
        )
        oldest_recent = min(recent_dates).isoformat() if recent_dates else None
        newest_recent = max(recent_dates).isoformat() if recent_dates else None
        timestamp_verified = sum(
            row.get("publication_timestamp_status") == "verified_from_sgml_header"
            for row in events
        )
        timestamp_unverified = len(events) - timestamp_verified
        report = {
            "cik": cik10,
            "ticker": ticker_value,
            "company_name": str(submissions.get("name") or ""),
            "requested_start_date": start.isoformat(),
            "requested_end_date": end.isoformat(),
            "collection_started_at_utc": collection_started,
            "collection_completed_at_utc": _utc_iso(self.now()),
            "recent_filings_oldest_date": oldest_recent,
            "recent_filings_newest_date": newest_recent,
            "recent_history_may_be_incomplete": history_may_be_incomplete,
            "uses_recent_submissions_only": True,
            "truncated_by_max_filings": truncated_by_limit,
            "candidate_count_in_requested_window": len(candidates),
            "selected_filing_count": len(selected),
            "event_count": len(events),
            "verified_header_timestamp_count": timestamp_verified,
            "unverified_header_timestamp_count": timestamp_unverified,
            "header_fetch_error_count": header_fetch_errors,
            "header_fetch_error_types": dict(sorted(header_fetch_error_types.items())),
            "header_http_status_counts": dict(sorted(header_http_status_counts.items())),
            "coverage_status": (
                "partial"
                if (
                    history_may_be_incomplete
                    or truncated_by_limit
                    or header_fetch_errors
                    or timestamp_unverified
                )
                else "bounded_recent_window"
            ),
            "historical_pit_warning": (
                "first_seen_at_utc starts at this collection run; these backfilled records "
                "must not be treated as known to the strategy at earlier historical decisions"
            ),
        }
        return {"metadata": report, "events": events}


def _safe_filing_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", required=True, help="JSON array of explicit {cik,ticker} pairs")
    parser.add_argument("--start-date", required=True, help="First SEC filing date to include (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="Last SEC filing date to include (YYYY-MM-DD)")
    parser.add_argument("--output", required=True, help="Path for normalized event JSON array")
    parser.add_argument("--metadata-output", help="Path for per-company coverage metadata JSON")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing snapshot; otherwise output paths are protected",
    )
    parser.add_argument("--max-filings-per-company", type=int, default=25)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--min-request-interval-seconds", type=float, default=0.15)
    parser.add_argument(
        "--user-agent",
        default=os.environ.get("SEC_USER_AGENT", ""),
        help="Application name and contact email; may also be set through SEC_USER_AGENT",
    )
    args = parser.parse_args(argv)

    try:
        universe = load_universe(args.universe)
        _as_date(args.start_date, "start_date")
        _as_date(args.end_date, "end_date")
        output_path = Path(args.output)
        metadata_path = Path(args.metadata_output) if args.metadata_output else output_path.with_suffix(".metadata.json")
        if output_path.resolve() == metadata_path.resolve():
            raise ValueError("event output and metadata output must be different files")
        existing_outputs = [path for path in (output_path, metadata_path) if path.exists()]
        if existing_outputs and not args.overwrite:
            names = ", ".join(str(path) for path in existing_outputs)
            raise ValueError(
                f"refusing to overwrite existing snapshot output(s): {names}; "
                "choose a new output path or explicitly pass --overwrite"
            )
        collector = SecEventCollector(
            args.user_agent,
            timeout_seconds=args.timeout_seconds,
            min_request_interval_seconds=args.min_request_interval_seconds,
        )
        all_events: list[dict[str, Any]] = []
        company_reports: list[dict[str, Any]] = []
        submission_errors = 0
        for company in universe:
            try:
                result = collector.collect_company(
                    company["cik"],
                    company["ticker"],
                    start_date=args.start_date,
                    end_date=args.end_date,
                    max_filings=args.max_filings_per_company,
                )
                company_reports.append(result["metadata"])
                all_events.extend(result["events"])
            except Exception as exc:
                submission_errors += 1
                company_reports.append({
                    "cik": company["cik"],
                    "ticker": company["ticker"],
                    "coverage_status": "submissions_fetch_error",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "event_count": 0,
                })

        all_events.sort(
            key=lambda row: (
                str(row.get("published_at_utc") or ""),
                str(row.get("tickers", [""])[0] if row.get("tickers") else ""),
                str(row.get("event_id") or ""),
            )
        )
        snapshot_json = json.dumps(
            all_events, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        )
        metadata = {
            "collector_version": "1.0",
            "source": "SEC EDGAR public submissions and filing index headers",
            "collection_finished_at_utc": _utc_iso(collector.now()),
            "requested_start_date": args.start_date,
            "requested_end_date": args.end_date,
            "universe_company_count": len(universe),
            "event_count": len(all_events),
            "event_snapshot_sha256": sha256(snapshot_json.encode("utf-8")).hexdigest(),
            "submissions_fetch_error_count": submission_errors,
            "companies_with_partial_coverage": sum(
                row.get("coverage_status") == "partial" for row in company_reports
            ),
            "company_reports": company_reports,
            "limitations": [
                "Only the submissions.recent table is read; older SEC filings.files archives are not downloaded.",
                "Historical events are stamped with their actual collector first-seen time, not a guessed historical observation time.",
                "The event timestamp from the SEC index header is an acceptance-time proxy, not proof of the exact time the event first reached any specific trading data feed.",
                "Ticker/CIK mappings must be supplied and versioned by the caller; current mappings are not a point-in-time historical mapping source.",
            ],
            "research_only": True,
            "production_scanner_modified": False,
        }
        output_path.write_text(json.dumps(all_events, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        metadata_path.write_text(json.dumps(metadata, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))

    print(f"Saved {len(all_events)} events to {output_path}")
    print(f"Saved collection metadata to {metadata_path}")
    if submission_errors == len(universe):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
