"""Capture a small set of current BLS macro series via the public API.

This is a current snapshot, not a historical vintage database. Each observation is
usable only at or after the actual retrieval timestamp. Revised values and
consensus surprises are not reconstructed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
_ALLOWED_HOST = "api.bls.gov"
SERIES = {
    "CUSR0000SA0": "cpi_all_items_sa",
    "CUSR0000SA0L1E": "cpi_less_food_energy_sa",
    "CES0000000001": "total_nonfarm_employment",
    "LNS14000000": "unemployment_rate",
    "CES0500000003": "average_hourly_earnings_private",
}


def _aware(value: str | datetime) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("retrieved_at_utc must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _latest_monthly(data: Any) -> dict[str, Any] | None:
    if not isinstance(data, list):
        return None
    candidates = []
    for row in data:
        if not isinstance(row, dict):
            continue
        year, period = str(row.get("year", "")), str(row.get("period", ""))
        if not (year.isdigit() and len(year) == 4 and period.startswith("M") and period[1:].isdigit()):
            continue
        month = int(period[1:])
        if not 1 <= month <= 12:
            continue
        raw = str(row.get("value", "")).strip().replace(",", "")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = None
        if value is not None and not math.isfinite(value):
            value = None
        candidates.append((int(year), month, row, value))
    if not candidates:
        return None
    year, month, row, value = max(candidates, key=lambda item: (item[0], item[1]))
    return {
        "observation_period": f"{year}-M{month:02d}",
        "year": year,
        "period": f"M{month:02d}",
        "period_name": row.get("periodName"),
        "value": value,
        "footnotes": row.get("footnotes", []),
        "latest_flag": row.get("latest"),
    }


def parse_bls_api_response(
    payload: bytes | str,
    *,
    retrieved_at_utc: str | datetime,
    source_url: str = API_URL,
) -> dict[str, Any]:
    retrieved = _aware(retrieved_at_utc)
    parsed = urlparse(source_url)
    if parsed.scheme != "https" or parsed.hostname != _ALLOWED_HOST:
        raise ValueError("BLS API URL failed official host allowlist")
    try:
        raw_bytes = payload.encode("utf-8") if isinstance(payload, str) else payload
        data = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise ValueError("invalid BLS API JSON response") from exc
    if data.get("status") != "REQUEST_SUCCEEDED":
        raise ValueError(f"BLS API request did not succeed: {data.get('status')}")
    series_data = data.get("Results", {}).get("series")
    if not isinstance(series_data, list):
        raise ValueError("BLS API response is missing Results.series")
    indexed = {str(row.get("seriesID")): row.get("data") for row in series_data if isinstance(row, dict)}
    records = []
    for series_id, label in SERIES.items():
        latest = _latest_monthly(indexed.get(series_id))
        records.append({
            "series_id": series_id,
            "series_label": label,
            "latest_observation": latest,
            "value_available": latest is not None and latest["value"] is not None,
            "available_at_utc": retrieved.isoformat().replace("+00:00", "Z"),
            "availability_rule": "usable_only_at_or_after_retrieved_at_utc",
            "research_only": True,
        })
    canonical = json.dumps(records, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return {
        "metadata": {
            "source": "us_bureau_of_labor_statistics_public_api",
            "source_url": source_url,
            "retrieved_at_utc": retrieved.isoformat().replace("+00:00", "Z"),
            "series_count": len(records),
            "available_series_count": sum(row["value_available"] for row in records),
            "source_payload_sha256": sha256(raw_bytes).hexdigest(),
            "normalized_rows_sha256": sha256(canonical.encode("utf-8")).hexdigest(),
            "api_status": data.get("status"),
            "research_only": True,
            "production_scanner_modified": False,
            "limitations": [
                "This is a current API snapshot, not a validated historical vintage series.",
                "Values may have been revised since their initial release; revisions are not reconstructed.",
                "No consensus estimate or release surprise is provided by this capture.",
                "Rows are usable only at or after retrieved_at_utc; historical observation periods do not imply historical availability.",
            ],
        },
        "series": records,
    }


def fetch_bls_macro_snapshot(
    *,
    start_year: int,
    end_year: int,
    opener: Callable[..., Any] | None = None,
    now: Callable[[], datetime] | None = None,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    current_year = datetime.now(timezone.utc).year
    if start_year < 1913 or end_year < start_year or end_year > current_year:
        raise ValueError("invalid BLS API year range")
    body = json.dumps({
        "seriesid": list(SERIES),
        "startyear": str(start_year),
        "endyear": str(end_year),
    }).encode("utf-8")
    request = Request(API_URL, data=body, headers={
        "User-Agent": "wijouyang-lab/us research collector (contact: 288002660+wijouyang-lab@users.noreply.github.com)",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }, method="POST")
    retrieved = (now or (lambda: datetime.now(timezone.utc)))()
    response = (opener or urlopen)(request, timeout=timeout_seconds)
    with response if hasattr(response, "__enter__") else _ResponseContext(response) as opened:
        payload = opened.read()
    return parse_bls_api_response(payload, retrieved_at_utc=retrieved, source_url=API_URL)


class _ResponseContext:
    def __init__(self, response: Any) -> None:
        self.response = response

    def __enter__(self) -> Any:
        return self.response

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        close = getattr(self.response, "close", None)
        if close:
            close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=datetime.now(timezone.utc).year - 2)
    parser.add_argument("--end-year", type=int, default=datetime.now(timezone.utc).year)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists():
        parser.error(f"refusing to overwrite existing snapshot: {output}")
    try:
        result = fetch_bls_macro_snapshot(start_year=args.start_year, end_year=args.end_year)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Captured {result['metadata']['available_series_count']}/{result['metadata']['series_count']} BLS series to {output}")
    print(f"Retrieval timestamp: {result['metadata']['retrieved_at_utc']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
