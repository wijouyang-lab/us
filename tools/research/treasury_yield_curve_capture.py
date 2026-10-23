"""Capture the official Treasury daily par yield curve for research-only use.

Historical XML rows are current downloads, not proof of historical point-in-time
availability. Each output row records the actual retrieval time and must not be
used for a decision timestamp earlier than that retrieval time unless a separately
validated historical publication timestamp is available.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

BASE_URL = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
DATA_KEY = "daily_treasury_yield_curve"
REAL_DATA_KEY = "daily_treasury_real_yield_curve"
_ALLOWED_HOST = "home.treasury.gov"
MATURITY_FIELDS = {
    "1m": "BC_1MONTH",
    "2m": "BC_2MONTH",
    "3m": "BC_3MONTH",
    "4m": "BC_4MONTH",
    "6m": "BC_6MONTH",
    "1y": "BC_1YEAR",
    "2y": "BC_2YEAR",
    "3y": "BC_3YEAR",
    "5y": "BC_5YEAR",
    "7y": "BC_7YEAR",
    "10y": "BC_10YEAR",
    "20y": "BC_20YEAR",
    "30y": "BC_30YEAR",
}
REAL_MATURITY_FIELDS = {
    "5y": "BC_5YEAR",
    "7y": "BC_7YEAR",
    "10y": "BC_10YEAR",
    "20y": "BC_20YEAR",
    "30y": "BC_30YEAR",
}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":")[-1].lower()


def _child_text(node: ET.Element, wanted: str) -> str:
    for child in node.iter():
        if _local_name(child.tag) == wanted.lower() and child is not node:
            return (child.text or "").strip()
    return ""


def _parse_yield(value: str) -> float | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        result = float(raw)
    except (TypeError, ValueError):
        return None
    return result if result == result and abs(result) != float("inf") else None


def _parse_date(value: str) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    # Treasury's OData XML usually emits ISO date-time; tolerate a date-only value.
    raw = raw.removeprefix("datetime'").removesuffix("'")
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        try:
            return datetime.strptime(raw[:10], "%Y-%m-%d").date().isoformat()
        except ValueError:
            return None


def parse_treasury_yield_curve_xml(
    payload: bytes | str,
    *,
    retrieved_at_utc: str | datetime,
    source_url: str,
    curve_type: str = "nominal",
) -> dict[str, Any]:
    """Normalize nominal or real Treasury Atom/OData XML without filling missing yields."""
    observed = retrieved_at_utc if isinstance(retrieved_at_utc, datetime) else datetime.fromisoformat(
        str(retrieved_at_utc).replace("Z", "+00:00")
    )
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("retrieved_at_utc must be timezone-aware")
    observed_iso = observed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    parsed_url = urlparse(source_url)
    if parsed_url.scheme != "https" or parsed_url.hostname != _ALLOWED_HOST:
        raise ValueError("source URL failed official Treasury host allowlist")
    try:
        root = ET.fromstring(payload)
    except (ET.ParseError, TypeError, ValueError) as exc:
        raise ValueError("invalid Treasury yield curve XML") from exc

    if curve_type not in {"nominal", "real"}:
        raise ValueError("curve_type must be nominal or real")
    maturity_fields = MATURITY_FIELDS if curve_type == "nominal" else REAL_MATURITY_FIELDS
    source_name = "us_treasury_daily_par_yield_curve" if curve_type == "nominal" else "us_treasury_daily_par_real_yield_curve"
    rows: list[dict[str, Any]] = []
    for entry in (node for node in root.iter() if _local_name(node.tag) == "entry"):
        date_raw = _child_text(entry, "NEW_DATE")
        observation_date = _parse_date(date_raw)
        if not observation_date:
            continue
        yields = {
            maturity: _parse_yield(_child_text(entry, xml_field))
            for maturity, xml_field in maturity_fields.items()
        }
        if not any(value is not None for value in yields.values()):
            continue
        y2, y3m, y10 = yields.get("2y"), yields.get("3m"), yields.get("10y")
        rows.append({
            "observation_date": observation_date,
            "yield_pct": yields,
            "slope_2s10s_bp": round((y10 - y2) * 100, 4) if y10 is not None and y2 is not None else None,
            "slope_3m10y_bp": round((y10 - y3m) * 100, 4) if y10 is not None and y3m is not None else None,
            "retrieved_at_utc": observed_iso,
            "source_url": source_url,
            "source": source_name,
            "availability_rule": "usable_only_at_or_after_retrieved_at_utc",
            "research_only": True,
        })
    rows.sort(key=lambda row: row["observation_date"])
    previous: dict[str, Any] | None = None
    for row in rows:
        current_yields = row["yield_pct"]
        prior_yields = previous.get("yield_pct", {}) if previous else {}
        for maturity in ("2y", "10y"):
            current, prior = current_yields.get(maturity), prior_yields.get(maturity)
            row[f"change_{maturity}_bp"] = (
                round((current - prior) * 100, 4)
                if current is not None and prior is not None else None
            )
        current_slope = row["slope_2s10s_bp"]
        prior_slope = previous.get("slope_2s10s_bp") if previous else None
        row["change_2s10s_bp"] = (
            round(current_slope - prior_slope, 4)
            if current_slope is not None and prior_slope is not None else None
        )
        previous = row
    canonical = json.dumps(rows, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return {
        "metadata": {
            "source": "us_treasury_daily_par_yield_curve",
            "source_url": source_url,
            "retrieved_at_utc": observed_iso,
            "source_payload_sha256": sha256(payload.encode("utf-8") if isinstance(payload, str) else payload).hexdigest(),
            "row_count": len(rows),
            "research_only": True,
            "production_scanner_modified": False,
            "limitations": [
                "A current historical download does not reconstruct when each historical value first became available.",
                "Rows are eligible only for decision timestamps at or after retrieved_at_utc unless a separate validated historical availability timestamp is supplied.",
                "Empty Treasury fields remain null and are never coerced to zero.",
                "Yield curve rates are Treasury's daily published par yields, not intraday executable bond prices.",
            ],
            "normalized_rows_sha256": sha256(canonical.encode("utf-8")).hexdigest(),
        },
        "rows": rows,
    }


def fetch_treasury_yield_curve(
    year: int,
    *,
    opener: Callable[..., Any] | None = None,
    now: Callable[[], datetime] | None = None,
    timeout_seconds: float = 20.0,
    curve_type: str = "nominal",
) -> dict[str, Any]:
    if year < 1990 or year > 9999:
        raise ValueError("year must be between 1990 and 9999")
    if curve_type not in {"nominal", "real"}:
        raise ValueError("curve_type must be nominal or real")
    data_key = DATA_KEY if curve_type == "nominal" else REAL_DATA_KEY
    url = BASE_URL + "?" + urlencode({
        "data": data_key,
        "field_tdr_date_value": str(year),
    })
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != _ALLOWED_HOST:
        raise ValueError("Treasury URL failed official host allowlist")
    request = Request(url, headers={
        "User-Agent": "us-quant-research/1.0 (research-only)",
        "Accept": "application/atom+xml, application/xml, text/xml",
    })
    response = (opener or urlopen)(request, timeout=timeout_seconds)
    with response if hasattr(response, "__enter__") else _ResponseContext(response) as opened:
        payload = opened.read()
    retrieved = (now or (lambda: datetime.now(timezone.utc)))()
    return parse_treasury_yield_curve_xml(payload, retrieved_at_utc=retrieved, source_url=url, curve_type=curve_type)


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
    parser.add_argument("--year", type=int, default=datetime.now(timezone.utc).year)
    parser.add_argument("--curve-type", choices=("nominal", "real"), default="nominal")
    parser.add_argument("--output", required=True, help="New immutable JSON snapshot path")
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists():
        parser.error(f"refusing to overwrite existing snapshot: {output}")
    try:
        result = fetch_treasury_yield_curve(args.year, curve_type=args.curve_type)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Captured {result['metadata']['row_count']} Treasury {args.curve_type} yield rows to {output}")
    print(f"Retrieval timestamp: {result['metadata']['retrieved_at_utc']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
