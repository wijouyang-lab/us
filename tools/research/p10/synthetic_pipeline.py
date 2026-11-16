"""Synthetic private-data gate for a Norgate-to-Actions pipeline.

Only synthetic data is used. The gate checks a signed bundle, US trading dates,
ticker/member-day coverage and rollback protection. It is not vendor evidence.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd

DATA_SCHEMA = "p10-norgate-synthetic-v2"
MANIFEST_SCHEMA = "p10-norgate-manifest-v1"
SOURCE = "norgate"
MAX_AGE_DAYS = 3
MEMBER_DAY_GATE = 0.95
TICKER_GATE = 0.98
REQUIRED_TICKERS = ("AAPL", "MSFT", "NVDA", "BRK.B", "WBA")
MEMBERSHIP_START = "2026-11-09"


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(payload: dict) -> str:
    return hashlib.sha256(canonical(payload)).hexdigest()


def _manifest_hmac(manifest: dict, key: str) -> str:
    signed = {k: manifest[k] for k in ("schema", "source", "version", "created_at", "data_sha256")}
    return hmac.new(key.encode("utf-8"), canonical(signed), hashlib.sha256).hexdigest()


def make_manifest(data: dict, key: str, version: int = 1, created_at: str | None = None) -> dict:
    m = {
        "schema": MANIFEST_SCHEMA,
        "source": SOURCE,
        "version": version,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "data_sha256": sha256(data),
    }
    m["hmac_sha256"] = _manifest_hmac(m, key)
    return m


def expected_last_us_session(as_of: datetime) -> date:
    """Return the last completed XNYS session, using exchange calendars."""
    cal = xcals.get_calendar("XNYS")
    local = as_of.astimezone(ZoneInfo("America/New_York"))
    ts = pd.Timestamp(local.date())
    if cal.is_session(ts):
        close = cal.session_close(ts).tz_convert(ZoneInfo("America/New_York"))
        if local < close:
            ts = cal.previous_session(ts)
    else:
        ts = cal.date_to_session(ts, direction="previous")
    return ts.date()


def build_synthetic_snapshot(as_of: datetime | None = None) -> dict:
    as_of = as_of or datetime(2026, 11, 13, 23, 0, tzinfo=timezone.utc)
    last = expected_last_us_session(as_of)
    cal = xcals.get_calendar("XNYS")
    sessions = [d.date() for d in cal.sessions_in_range(MEMBERSHIP_START, last.isoformat())]
    ohlcv = []
    membership = []
    for i, ticker in enumerate(REQUIRED_TICKERS):
        for j, d in enumerate(sessions):
            close = 100.0 + i * 10 + j
            ohlcv.append({
                "ticker": ticker, "assetid": 1000 + i, "date": d.isoformat(),
                "open": close - 0.5, "high": close + 1.0,
                "low": close - 1.0, "close": close, "volume": 1_000_000 + j,
            })
            membership.append({
                "ticker": ticker, "assetid": 1000 + i, "date": d.isoformat(),
                "effective_date": d.isoformat(), "is_member": True,
            })
    return {
        "schema": DATA_SCHEMA,
        "source": SOURCE,
        "scope": "TRIAL_MECHANICS",
        "synthetic": True,
        "data_updated_at": as_of.isoformat(),
        "expected_last_us_session": last.isoformat(),
        "latest_price_date": last.isoformat(),
        "membership_latest_date": last.isoformat(),
        "per_ticker_latest_price_date": {t: last.isoformat() for t in REQUIRED_TICKERS},
        "expected_tickers": list(REQUIRED_TICKERS),
        "membership_start_date": MEMBERSHIP_START,
        "ohlcv": ohlcv,
        "membership": membership,
        "assetid_map": [{"ticker": t, "assetid": 1000 + i} for i, t in enumerate(REQUIRED_TICKERS)],
    }


def write_bundle(directory: Path, data: dict, key: str, version: int = 1) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    data_path = directory / "snapshot.json"
    manifest_path = directory / "manifest.json"
    data_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    manifest_path.write_text(json.dumps(make_manifest(data, key, version), indent=2, sort_keys=True), encoding="utf-8")
    return data_path, manifest_path


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def validate_bundle(
    data_path: Path,
    manifest_path: Path,
    key: str,
    *,
    now: datetime | None = None,
    state_path: Path | None = None,
    expected_scope: str = "TRIAL_MECHANICS",
    max_age_days: int = MAX_AGE_DAYS,
    member_day_gate: float = MEMBER_DAY_GATE,
    ticker_gate: float = TICKER_GATE,
) -> dict:
    """Validate a synthetic bundle; fail closed on any unsafe condition."""
    now = now or datetime.now(timezone.utc)
    errors: list[str] = []
    metrics: dict[str, float | int | str] = {}
    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"ok": False, "errors": ["MISSING_OR_CORRUPT_BUNDLE"], "metrics": {}, "synthetic": True}

    if data.get("schema") != DATA_SCHEMA:
        errors.append("SCHEMA_MISMATCH")
    if data.get("source") != SOURCE:
        errors.append("SOURCE_MISMATCH")
    if data.get("scope") != expected_scope:
        errors.append("SCOPE_MISMATCH")
    if data.get("synthetic") is not True:
        errors.append("NOT_SYNTHETIC")
    if manifest.get("schema") != MANIFEST_SCHEMA:
        errors.append("MANIFEST_SCHEMA_MISMATCH")
    if manifest.get("source") != SOURCE:
        errors.append("MANIFEST_SOURCE_MISMATCH")

    actual_digest = sha256(data)
    metrics["data_sha256"] = actual_digest
    if manifest.get("data_sha256") != actual_digest:
        errors.append("SHA256_MISMATCH")
    supplied_hmac = manifest.get("hmac_sha256")
    if not supplied_hmac:
        errors.append("MISSING_SIGNATURE")
    elif not hmac.compare_digest(supplied_hmac, _manifest_hmac(manifest, key)):
        errors.append("HMAC_MISMATCH")

    version = manifest.get("version")
    metrics["version"] = version if isinstance(version, int) else -1
    if state_path and state_path.exists() and isinstance(version, int):
        last = json.loads(state_path.read_text(encoding="utf-8")).get("last_version", 0)
        if version < last:
            errors.append(f"ROLLBACK version={version} last={last}")
        elif version == last:
            errors.append(f"DUPLICATE_VERSION version={version}")

    try:
        expected = expected_last_us_session(now)
        metrics["expected_last_us_session"] = expected.isoformat()
    except Exception:
        errors.append("CALENDAR_UNAVAILABLE")
        expected = None

    if expected:
        if data.get("expected_last_us_session") != expected.isoformat():
            errors.append("EXPECTED_SESSION_MISMATCH")
        latest = data.get("latest_price_date")
        if latest != expected.isoformat():
            errors.append(f"LATEST_PRICE_DATE_LAG latest={latest} expected={expected.isoformat()}")
        if data.get("membership_latest_date") != expected.isoformat():
            errors.append("MEMBERSHIP_LATEST_LAG")
        for ticker, d in (data.get("per_ticker_latest_price_date") or {}).items():
            if d != expected.isoformat():
                errors.append(f"PER_TICKER_LATEST_MISSING {ticker}")
        for ticker in data.get("expected_tickers", []):
            if ticker not in (data.get("per_ticker_latest_price_date") or {}):
                errors.append(f"PER_TICKER_LATEST_MISSING {ticker}")

    try:
        updated = datetime.fromisoformat(data["data_updated_at"])
        if updated.tzinfo is None:
            raise ValueError
        age = (now - updated).total_seconds() / 86400
        metrics["age_days"] = round(age, 3)
        if age > max_age_days:
            errors.append(f"STALE_DATA age_days={age:.2f}")
        if age < -1:
            errors.append("FUTURE_DATA_UPDATED_AT")
    except (KeyError, TypeError, ValueError):
        errors.append("INVALID_DATA_UPDATED_AT")

    expected_tickers = set(data.get("expected_tickers", []))
    actual_tickers = {r["ticker"] for r in data.get("ohlcv", [])}
    missing = expected_tickers - actual_tickers
    if missing:
        errors.append("MISSING_TICKER " + ",".join(sorted(missing)))
    ticker_cov = len(expected_tickers & actual_tickers) / len(expected_tickers) if expected_tickers else 0
    metrics["ticker_coverage"] = round(ticker_cov, 4)
    if ticker_cov < ticker_gate:
        errors.append(f"TICKER_COVERAGE_LOW {ticker_cov:.4f}")

    seen = set()
    for r in data.get("ohlcv", []):
        key2 = (r.get("ticker"), r.get("date"))
        if key2 in seen:
            errors.append(f"DUPLICATE_OHLCV {key2[0]} {key2[1]}")
        seen.add(key2)
        if not all(float(r.get(k, 0)) > 0 for k in ("open", "high", "low", "close")):
            errors.append(f"BAD_OHLCV {key2[0]} {key2[1]}")
            break
        if not (float(r["low"]) <= float(r["close"]) <= float(r["high"])):
            errors.append(f"BAD_OHLCV_RANGE {key2[0]} {key2[1]}")
            break

    membership = data.get("membership", [])
    if not membership:
        errors.append("MISSING_MEMBERSHIP")
    membership_seen = set()
    for r in membership:
        key2 = (r.get("ticker"), r.get("date"))
        if key2 in membership_seen:
            errors.append(f"DUPLICATE_MEMBERSHIP {key2[0]} {key2[1]}")
        membership_seen.add(key2)

    if expected:
        cal = xcals.get_calendar("XNYS")
        start = data.get("membership_start_date", MEMBERSHIP_START)
        sessions = [d.date() for d in cal.sessions_in_range(start, expected.isoformat())]
        expected_member_days = len(expected_tickers) * len(sessions)
        actual_member_days = len({
            (r["ticker"], r["date"]) for r in membership if r.get("is_member") is True
        })
        member_cov = actual_member_days / expected_member_days if expected_member_days else 0
        metrics["member_day_coverage"] = round(member_cov, 4)
        if member_cov < member_day_gate:
            errors.append(f"MEMBER_DAY_COVERAGE_LOW {member_cov:.4f}")
        daily = []
        for d in sessions:
            got = len({r["ticker"] for r in membership if r["date"] == d.isoformat() and r.get("is_member") is True})
            daily.append(got / len(expected_tickers) if expected_tickers else 0)
        metrics["min_daily_membership_completeness"] = round(min(daily), 4) if daily else 0
        if daily and min(daily) < 1.0:
            errors.append(f"MEMBERSHIP_DAY_INCOMPLETE min={min(daily):.4f}")
    return {"ok": not errors, "errors": errors, "metrics": metrics, "synthetic": True}
