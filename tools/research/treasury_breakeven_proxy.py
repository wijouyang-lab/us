"""Combine nominal and real Treasury curves into a research-only breakeven proxy.

The nominal-minus-real spread is an inflation-compensation proxy, not a pure
expectation measure: it can include inflation-risk and liquidity premia. Since
source snapshots may be downloaded historically today, output rows are only
available from the later of the two snapshot retrieval timestamps.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


def _aware_utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp")
    return parsed.astimezone(timezone.utc)


def build_breakeven_proxy(
    nominal_snapshot: dict[str, Any],
    real_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Join same-date yields and calculate nominal-minus-real spreads in bp."""
    nm = nominal_snapshot.get("metadata", {})
    rm = real_snapshot.get("metadata", {})
    if nm.get("curve_type", "nominal") != "nominal":
        raise ValueError("nominal snapshot metadata must identify curve_type=nominal")
    if rm.get("curve_type") != "real":
        raise ValueError("real snapshot metadata must identify curve_type=real")
    nominal_retrieved = _aware_utc(nm.get("retrieved_at_utc"), "nominal retrieved_at_utc")
    real_retrieved = _aware_utc(rm.get("retrieved_at_utc"), "real retrieved_at_utc")
    available_at = max(nominal_retrieved, real_retrieved)

    def validate_source_url(value: Any, expected_data_key: str, label: str) -> str:
        if not isinstance(value, str) or not value:
            raise ValueError(f"{label} source_url is required")
        parsed = urlparse(value)
        query = parse_qs(parsed.query)
        if parsed.scheme != "https" or parsed.hostname != "home.treasury.gov":
            raise ValueError(f"{label} source_url must use the official HTTPS Treasury host")
        if query.get("data") != [expected_data_key]:
            raise ValueError(f"{label} source_url has an unexpected Treasury data key")
        return value

    nominal_source_url = validate_source_url(
        nm.get("source_url"), "daily_treasury_yield_curve", "nominal"
    )
    real_source_url = validate_source_url(
        rm.get("source_url"), "daily_treasury_real_yield_curve", "real"
    )
    nominal_rows = nominal_snapshot.get("rows")
    real_rows = real_snapshot.get("rows")
    if not isinstance(nominal_rows, list) or not isinstance(real_rows, list):
        raise ValueError("both snapshots must contain a rows array")

    def by_date(rows: list[Any], label: str) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            date = row.get("observation_date")
            if not isinstance(date, str) or not date:
                continue
            if date in result:
                raise ValueError(f"duplicate observation_date in {label} snapshot: {date}")
            result[date] = row
        return result

    nominal_by_date = by_date(nominal_rows, "nominal")
    real_by_date = by_date(real_rows, "real")
    for label, indexed, retrieved in (("nominal", nominal_by_date, nominal_retrieved), ("real", real_by_date, real_retrieved)):
        future_dates = sorted(date for date in indexed if date > retrieved.date().isoformat())
        if future_dates:
            raise ValueError(f"{label} snapshot contains observation dates after retrieval date: {future_dates[0]}")
    maturities = ("5y", "7y", "10y", "20y", "30y")
    rows: list[dict[str, Any]] = []
    for date in sorted(nominal_by_date.keys() & real_by_date.keys()):
        ny = nominal_by_date[date].get("yield_pct", {})
        ry = real_by_date[date].get("yield_pct", {})
        spreads: dict[str, float | None] = {}
        for maturity in maturities:
            n, r = ny.get(maturity), ry.get(maturity)
            if n is None or r is None:
                spreads[maturity] = None
                continue
            try:
                nominal_yield, real_yield = float(n), float(r)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"non-numeric yield for {date} {maturity}") from exc
            if not math.isfinite(nominal_yield) or not math.isfinite(real_yield):
                raise ValueError(f"non-finite yield for {date} {maturity}")
            spreads[maturity] = round((nominal_yield - real_yield) * 100, 4)
        rows.append({
            "observation_date": date,
            "breakeven_proxy_bp": spreads,
            "available_at_utc": available_at.isoformat().replace("+00:00", "Z"),
            "nominal_retrieved_at_utc": nominal_retrieved.isoformat().replace("+00:00", "Z"),
            "real_retrieved_at_utc": real_retrieved.isoformat().replace("+00:00", "Z"),
            "source": "us_treasury_nominal_minus_real_yield_proxy",
            "source_nominal_url": nominal_source_url,
            "source_real_url": real_source_url,
            "availability_rule": "usable_only_at_or_after_available_at_utc",
            "research_only": True,
        })
    canonical = json.dumps(rows, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return {
        "metadata": {
            "source": "us_treasury_nominal_minus_real_yield_proxy",
            "curve_type": "breakeven_proxy",
            "nominal_retrieved_at_utc": nominal_retrieved.isoformat().replace("+00:00", "Z"),
            "real_retrieved_at_utc": real_retrieved.isoformat().replace("+00:00", "Z"),
            "available_at_utc": available_at.isoformat().replace("+00:00", "Z"),
            "row_count": len(rows),
            "matched_observation_dates": len(rows),
            "unmatched_nominal_dates": len(nominal_by_date.keys() - real_by_date.keys()),
            "unmatched_real_dates": len(real_by_date.keys() - nominal_by_date.keys()),
            "research_only": True,
            "production_scanner_modified": False,
            "limitations": [
                "Nominal-minus-real yield is an inflation-compensation proxy, not a pure expected-inflation measure; it can include risk and liquidity premia.",
                "Rows are usable only at or after available_at_utc, the later of the two actual snapshot retrieval timestamps.",
                "A historical observation date does not establish historical point-in-time availability.",
                "Maturities without both nominal and real values remain null; no interpolation or zero fill is performed.",
            ],
            "rows_sha256": sha256(canonical.encode("utf-8")).hexdigest(),
        },
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nominal", required=True, help="Nominal curve JSON snapshot")
    parser.add_argument("--real", required=True, help="Real curve JSON snapshot")
    parser.add_argument("--output", required=True, help="New immutable output JSON path")
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists():
        parser.error(f"refusing to overwrite existing output: {output}")
    try:
        nominal = json.loads(Path(args.nominal).read_text(encoding="utf-8"))
        real = json.loads(Path(args.real).read_text(encoding="utf-8"))
        result = build_breakeven_proxy(nominal, real)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Matched {result['metadata']['row_count']} dates; output: {output}")
    print(f"Available no earlier than {result['metadata']['available_at_utc']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
