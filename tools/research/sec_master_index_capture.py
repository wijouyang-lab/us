"""Capture SEC EDGAR master.idx as research-only filing metadata.

This is a bounded, one-request-per-quarter fallback. It does not infer
intraday publication timestamps or historical first-seen availability.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from tools.research.sec_daily_index import parse_sec_master_index

_ALLOWED_HOST = "www.sec.gov"
_BASE_URL = "https://www.sec.gov/Archives/edgar/daily-index"


def _utc(value: str | datetime) -> str:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("retrieved_at_utc must be timezone-aware")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_master_index_url(start_date: str, end_date: str) -> str:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if start > end:
        raise ValueError("start_date must not be after end_date")
    if (start.year, (start.month - 1) // 3) != (end.year, (end.month - 1) // 3):
        raise ValueError("SEC master.idx fallback supports a single calendar quarter per request")
    quarter = (start.month - 1) // 3 + 1
    return f"{_BASE_URL}/{start.year}/QTR{quarter}/master.idx"


def fetch_master_index(
    *,
    cik_tickers: dict[str, str],
    start_date: str,
    end_date: str,
    user_agent: str,
    opener: Callable[..., Any] | None = None,
    now: Callable[[], datetime] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    minimum_interval_seconds: float = 0.12,
    timeout_seconds: float = 25.0,
) -> dict[str, Any]:
    """Fetch one official quarterly index and parse only the requested CIK/date range."""
    if not isinstance(user_agent, str) or not user_agent.strip() or "@" not in user_agent:
        raise ValueError("an identifiable SEC User-Agent with contact information is required")
    if minimum_interval_seconds < 0.1:
        raise ValueError("minimum_interval_seconds must be at least 0.1")
    url = build_master_index_url(start_date, end_date)
    parsed_url = urlparse(url)
    if parsed_url.scheme != "https" or parsed_url.hostname != _ALLOWED_HOST:
        raise ValueError("SEC master index URL failed official host allowlist")
    request = Request(url, headers={"User-Agent": user_agent.strip(), "Accept": "text/plain"})
    sleep(minimum_interval_seconds)
    try:
        response = (opener or urlopen)(request, timeout=timeout_seconds)
        with response if hasattr(response, "__enter__") else _ResponseContext(response) as opened:
            payload = opened.read()
    except HTTPError as exc:
        raise RuntimeError(f"SEC master index HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"SEC master index network error: {type(exc).__name__}: {exc}") from exc
    try:
        text_payload = payload.decode("utf-8-sig") if isinstance(payload, bytes) else str(payload)
    except UnicodeDecodeError as exc:
        raise ValueError("SEC master index is not valid UTF-8") from exc
    if "CIK|Company Name|Form Type|Date Filed|Filename" not in text_payload:
        raise ValueError("SEC master index response is missing the expected header")
    retrieved_at = _utc((now or (lambda: datetime.now(timezone.utc)))())
    parsed = parse_sec_master_index(
        text_payload, cik_tickers=cik_tickers, start_date=start_date, end_date=end_date
    )
    raw_bytes = payload if isinstance(payload, bytes) else text_payload.encode("utf-8")
    parsed["metadata"].update({
        "source_url": url,
        "retrieved_at_utc": retrieved_at,
        "source_payload_sha256": sha256(raw_bytes).hexdigest(),
        "request_status": "success",
        "historical_pit_eligible": False,
        "limitations": list(parsed["metadata"]["limitations"]) + [
            "The quarterly master index is a current download and does not prove when an individual filing became publicly available.",
            "Events remain ineligible for historical decisions without an independently verified publication timestamp and historical first-seen evidence.",
        ],
    })
    for event in parsed["events"]:
        event["first_seen_at_utc"] = retrieved_at
        event["first_seen_basis"] = "collector_observed_quarterly_index"
    return parsed


class _ResponseContext:
    def __init__(self, response: Any) -> None:
        self.response = response

    def __enter__(self) -> Any:
        return self.response

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        close = getattr(self.response, "close", None)
        if close:
            close()


def _load_universe(path: str) -> dict[str, str]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("universe must be a JSON array of CIK/ticker objects")
    result: dict[str, str] = {}
    for row in payload:
        if not isinstance(row, dict) or not row.get("cik") or not row.get("ticker"):
            continue
        result[str(row["cik"])] = str(row["ticker"])
    if not result:
        raise ValueError("universe contains no valid CIK/ticker pairs")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", required=True, help="Explicit current CIK/ticker JSON universe")
    parser.add_argument("--start-date", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--output", required=True, help="New immutable output JSON path")
    parser.add_argument("--user-agent", default=os.environ.get("SEC_USER_AGENT", ""))
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists():
        parser.error(f"refusing to overwrite existing output: {output}")
    try:
        result = fetch_master_index(
            cik_tickers=_load_universe(args.universe),
            start_date=args.start_date,
            end_date=args.end_date,
            user_agent=args.user_agent,
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(f"Captured {result['metadata']['event_count']} SEC master-index events to {output}")
    print(f"Retrieved at {result['metadata']['retrieved_at_utc']}; historical PIT eligible: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
