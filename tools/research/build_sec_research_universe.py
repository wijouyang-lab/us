"""Resolve a current explicit ticker watchlist to SEC CIKs for prospective research capture.

The result is a point-in-time mapping snapshot, not a historical constituent list.
It never infers past membership and does not create event labels.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_ALLOWED_HOST = "www.sec.gov"


def _utc(value: str | datetime) -> str:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("retrieved_at_utc must be timezone-aware")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _ticker_key(value: Any) -> str:
    return str(value or "").strip().upper().replace("$", "").replace("-", ".")


def load_requested_tickers(path: str | Path) -> list[str]:
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"cannot read ticker list: {exc}") from exc
    tickers = list(dict.fromkeys(line.strip().upper().replace("$", "") for line in lines if line.strip() and not line.lstrip().startswith("#")))
    if not tickers:
        raise ValueError("ticker list must contain at least one ticker")
    return tickers


def build_sec_universe(
    requested_tickers: list[str],
    payload: bytes | str,
    *,
    retrieved_at_utc: str | datetime,
    source_url: str = SEC_TICKERS_URL,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    retrieved = _utc(retrieved_at_utc)
    parsed_url = urlparse(source_url)
    if parsed_url.scheme != "https" or parsed_url.hostname != _ALLOWED_HOST:
        raise ValueError("SEC ticker URL failed official host allowlist")
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise ValueError("invalid SEC company ticker JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("SEC company ticker response must be a JSON object")
    lookup: dict[str, dict[str, str]] = {}
    for row in data.values():
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        cik_raw = row.get("cik_str")
        try:
            cik_num = int(cik_raw)
        except (TypeError, ValueError):
            continue
        if not ticker or cik_num < 1:
            continue
        lookup[_ticker_key(ticker)] = {"cik": str(cik_num).zfill(10), "ticker": ticker}
    result: list[dict[str, str]] = []
    matched: list[str] = []
    unmatched: list[str] = []
    seen_ciks: set[str] = set()
    for ticker in requested_tickers:
        row = lookup.get(_ticker_key(ticker))
        if row is None:
            unmatched.append(ticker)
            continue
        if row["cik"] in seen_ciks:
            continue
        seen_ciks.add(row["cik"])
        result.append({"cik": row["cik"], "ticker": ticker})
        matched.append(ticker)
    if not result:
        raise ValueError("none of the requested tickers matched the official SEC company ticker list")
    metadata = {
        "source": "sec_company_tickers_json",
        "source_url": source_url,
        "retrieved_at_utc": retrieved,
        "source_payload_sha256": sha256(raw).hexdigest(),
        "requested_tickers": requested_tickers,
        "matched_tickers": matched,
        "unmatched_tickers": unmatched,
        "matched_count": len(result),
        "research_only": True,
        "historical_membership_inferred": False,
        "limitations": [
            "This is the current SEC ticker-to-CIK mapping snapshot for prospective capture, not a historical ticker mapping.",
            "Ticker aliases and share classes may not match exactly; unmatched tickers are reported, never guessed.",
            "SEC filing observations are only point-in-time usable from their actual first-seen capture time unless independent historical availability is validated.",
        ],
    }
    return result, metadata


def fetch_sec_universe(
    requested_tickers: list[str],
    *,
    user_agent: str,
    opener: Callable[..., Any] | None = None,
    now: Callable[[], datetime] | None = None,
    timeout_seconds: float = 20.0,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    if not isinstance(user_agent, str) or "@" not in user_agent or not user_agent.strip():
        raise ValueError("SEC User-Agent must identify the research application and a contact email")
    request = Request(SEC_TICKERS_URL, headers={
        "User-Agent": user_agent.strip(),
        "Accept": "application/json",
    })
    response = (opener or urlopen)(request, timeout=timeout_seconds)
    with response if hasattr(response, "__enter__") else _ResponseContext(response) as opened:
        payload = opened.read()
    retrieved = (now or (lambda: datetime.now(timezone.utc)))()
    return build_sec_universe(requested_tickers, payload, retrieved_at_utc=retrieved)


class _ResponseContext:
    def __init__(self, response: Any):
        self.response = response

    def __enter__(self):
        return self.response

    def __exit__(self, exc_type, exc, tb):
        close = getattr(self.response, "close", None)
        if close:
            close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickers-file", required=True, help="One ticker per line")
    parser.add_argument("--output", required=True, help="New JSON array for sec_event_collector")
    parser.add_argument("--metadata-output", required=True, help="New mapping provenance JSON")
    parser.add_argument("--user-agent", default=os.environ.get("SEC_USER_AGENT", ""))
    args = parser.parse_args(argv)
    outputs = [Path(args.output), Path(args.metadata_output)]
    if any(path.exists() for path in outputs):
        parser.error("refusing to overwrite an existing SEC universe snapshot")
    try:
        requested = load_requested_tickers(args.tickers_file)
        universe, metadata = fetch_sec_universe(requested, user_agent=args.user_agent)
        outputs[0].parent.mkdir(parents=True, exist_ok=True)
        outputs[1].parent.mkdir(parents=True, exist_ok=True)
        outputs[0].write_text(json.dumps(universe, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        outputs[1].write_text(json.dumps(metadata, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Mapped {len(universe)} of {len(requested)} requested tickers to SEC CIKs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
