"""Synthetic Norgate-compatible snapshot gate.

No vendor data is used. This tests the interface between a Windows Norgate
export and GitHub Actions: schema, SHA256, ticker coverage and staleness.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

REQUIRED_TICKERS = ("AAPL", "MSFT", "NVDA", "BRK.B", "WBA")
MAX_STALENESS_DAYS = 3


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(payload: dict) -> str:
    return hashlib.sha256(_canonical(payload)).hexdigest()


def build_synthetic_snapshot(as_of: date = date(2026, 11, 13)) -> dict:
    """Build deterministic synthetic OHLCV + PIT membership + assetid data."""
    rows = []
    dates = ["2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13"]
    for i, ticker in enumerate(REQUIRED_TICKERS):
        for j, d in enumerate(dates):
            close = 100.0 + i * 10 + j
            rows.append({
                "ticker": ticker,
                "assetid": 1000 + i,
                "date": d,
                "open": close - 0.5,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 1_000_000 + j * 1000,
            })
    membership = []
    for i, d in enumerate(dates):
        for j, ticker in enumerate(REQUIRED_TICKERS):
            membership.append({
                "date": d,
                "ticker": ticker,
                "assetid": 1000 + j,
                "effective_date": "2026-11-09",
                "is_member": ticker != "WBA",
            })
    payload = {
        "schema": "p10-norgate-synthetic-v1",
        "data_updated_at": f"{as_of.isoformat()}T22:00:00+00:00",
        "ohlcv": rows,
        "membership": membership,
        "synthetic": True,
    }
    payload["sha256"] = _digest(payload)
    return payload


def write_snapshot(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def validate_snapshot(
    path: Path,
    now: datetime | None = None,
    max_age_days: int = MAX_STALENESS_DAYS,
) -> tuple[bool, list[str]]:
    """Fail closed on corrupt, stale or incomplete snapshots."""
    now = now or datetime.now(timezone.utc)
    payload = json.loads(path.read_text(encoding="utf-8"))
    supplied = payload.pop("sha256", None)
    errors: list[str] = []
    if supplied != _digest(payload):
        errors.append("SHA256_MISMATCH")
    try:
        updated = datetime.fromisoformat(payload["data_updated_at"])
        if updated.tzinfo is None:
            raise ValueError("timezone required")
    except (KeyError, TypeError, ValueError):
        errors.append("INVALID_DATA_UPDATED_AT")
        updated = None
    if updated is not None:
        age = (now - updated).total_seconds() / 86400
        if age > max_age_days:
            errors.append(f"STALE_DATA age_days={age:.2f}")
        if age < -1:
            errors.append("FUTURE_DATA_UPDATED_AT")
    tickers = {r["ticker"] for r in payload.get("ohlcv", [])}
    for required in REQUIRED_TICKERS:
        if required not in tickers:
            errors.append(f"MISSING_TICKER {required}")
    for r in payload.get("ohlcv", []):
        if not all(float(r.get(k, 0)) > 0 for k in ("open", "high", "low", "close")):
            errors.append(f"BAD_OHLCV {r.get('ticker')} {r.get('date')}")
            break
    if not payload.get("membership"):
        errors.append("MISSING_MEMBERSHIP")
    if not payload.get("synthetic"):
        errors.append("NOT_SYNTHETIC")
    return (not errors, errors)
