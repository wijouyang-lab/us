"""Synthetic private-data gate for a Norgate-to-Actions pipeline.

All data is SYNTHETIC. The gate derives dates from actual OHLCV/membership rows,
not from metadata claims. Production must use Ed25519/KMS and durable state.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd

DATA_SCHEMA = "p10-norgate-synthetic-v3"
MANIFEST_SCHEMA = "p10-norgate-manifest-v1"
SOURCE = "norgate"
MAX_AGE_DAYS = 3
MEMBER_DAY_GATE = 0.95
TICKER_GATE = 0.98
P9_START = date(2007, 5, 30)
P9_END = date(2024, 12, 31)
TRIAL_MAX_YEARS = 2
CORE_TICKERS = ("AAPL", "MSFT", "NVDA", "BRK.B", "WBA")


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(payload: dict) -> str:
    return hashlib.sha256(canonical(payload)).hexdigest()


def _manifest_hmac(manifest: dict, key: str) -> str:
    signed = {k: manifest[k] for k in ("schema", "source", "version", "created_at", "data_sha256")}
    return hmac.new(key.encode("utf-8"), canonical(signed), hashlib.sha256).hexdigest()


def make_manifest(data: dict, key: str, version: int = 1) -> dict:
    m = {
        "schema": MANIFEST_SCHEMA,
        "source": SOURCE,
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data_sha256": sha256(data),
    }
    m["hmac_sha256"] = _manifest_hmac(m, key)
    return m


def expected_last_us_session(as_of: datetime) -> date:
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


def _sessions(start: date, end: date) -> list[date]:
    cal = xcals.get_calendar("XNYS")
    return [d.date() for d in cal.sessions_in_range(start.isoformat(), end.isoformat())]


def _make_tickers(count: int) -> list[str]:
    names = list(CORE_TICKERS)
    i = 0
    while len(names) < count:
        names.append(f"T{i:03d}")
        i += 1
    return names[:count]


def build_synthetic_snapshot(
    now: datetime | None = None,
    *,
    scope: str = "TRIAL_MECHANICS",
    ticker_count: int = 50,
    trial_start_date: date | None = None,
) -> dict:
    now = now or datetime(2026, 11, 13, 23, 0, tzinfo=timezone.utc)
    tickers = _make_tickers(ticker_count)
    if scope == "P9_FULL_HISTORY":
        start, end = P9_START, P9_END
        updated = datetime(2025, 1, 1, 1, 0, tzinfo=timezone.utc)
    elif scope == "TRIAL_MECHANICS":
        trial_start_date = trial_start_date or date(2026, 11, 13)
        end = expected_last_us_session(now)
        start = _sessions(date(2026, 11, 9), end)[0]
        updated = now
    else:
        raise ValueError("unknown scope")
    sessions = _sessions(start, end)
    ohlcv, membership = [], []
    for i, ticker in enumerate(tickers):
        for j, d in enumerate(sessions):
            close = 100.0 + i + j * 0.01
            ohlcv.append({
                "ticker": ticker, "assetid": 1000 + i, "date": d.isoformat(),
                "open": close - 0.5, "high": close + 1.0,
                "low": close - 1.0, "close": close, "volume": 1_000_000 + j,
            })
            membership.append({
                "ticker": ticker, "assetid": 1000 + i, "date": d.isoformat(),
                "effective_date": d.isoformat(), "is_member": True,
            })
    expected_membership = [dict(r) for r in membership]
    data = {
        "schema": DATA_SCHEMA,
        "source": SOURCE,
        "scope": scope,
        "synthetic": True,
        "data_updated_at": updated.isoformat(),
        "expected_tickers": tickers,
        "core_tickers": list(CORE_TICKERS),
        "trial_start_date": trial_start_date.isoformat() if trial_start_date else None,
        "ohlcv": ohlcv,
        "membership": membership,
        "expected_membership": expected_membership,
        "assetid_map": [{"ticker": t, "assetid": 1000 + i} for i, t in enumerate(tickers)],
    }
    # Deliberately keep a reported field to test that it is not trusted.
    data["reported_latest_price_date"] = end.isoformat()
    data["reported_membership_latest_date"] = end.isoformat()
    return data


def write_bundle(directory: Path, data: dict, key: str, version: int = 1) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    data_path = directory / "snapshot.json"
    manifest_path = directory / "manifest.json"
    data_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    manifest_path.write_text(json.dumps(make_manifest(data, key, version), indent=2, sort_keys=True), encoding="utf-8")
    return data_path, manifest_path


def _finite(value) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _actual_dates(data: dict) -> tuple[date | None, dict[str, date], date | None]:
    rows = data.get("ohlcv", [])
    if not rows:
        return None, {}, None
    overall = max(date.fromisoformat(r["date"]) for r in rows)
    per: dict[str, date] = {}
    for r in rows:
        d = date.fromisoformat(r["date"])
        per[r["ticker"]] = max(per.get(r["ticker"], d), d)
    mrows = data.get("membership", [])
    mdate = max((date.fromisoformat(r["date"]) for r in mrows), default=None)
    return overall, per, mdate


def validate_bundle(
    data_path: Path,
    manifest_path: Path,
    key: str,
    *,
    now: datetime | None = None,
    state_path: Path | None = None,
    expected_scope: str | None = None,
    max_age_days: int = MAX_AGE_DAYS,
    member_day_gate: float = MEMBER_DAY_GATE,
    ticker_gate: float = TICKER_GATE,
) -> dict:
    now = now or datetime.now(timezone.utc)
    errors: list[str] = []
    metrics: dict = {}
    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"ok": False, "errors": ["MISSING_OR_CORRUPT_BUNDLE"], "metrics": {}, "synthetic": True}

    if data.get("schema") != DATA_SCHEMA:
        errors.append("SCHEMA_MISMATCH")
    if data.get("source") != SOURCE:
        errors.append("SOURCE_MISMATCH")
    if expected_scope and data.get("scope") != expected_scope:
        errors.append("SCOPE_MISMATCH")
    if data.get("synthetic") is not True:
        errors.append("NOT_SYNTHETIC")
    if manifest.get("schema") != MANIFEST_SCHEMA or manifest.get("source") != SOURCE:
        errors.append("MANIFEST_SCHEMA_OR_SOURCE_MISMATCH")

    digest = sha256(data)
    metrics["data_sha256"] = digest
    if manifest.get("data_sha256") != digest:
        errors.append("SHA256_MISMATCH")
    if not manifest.get("hmac_sha256"):
        errors.append("MISSING_SIGNATURE")
    elif not hmac.compare_digest(manifest["hmac_sha256"], _manifest_hmac(manifest, key)):
        errors.append("HMAC_MISMATCH")

    version = manifest.get("version")
    metrics["version"] = version
    last = 0
    if state_path and state_path.exists():
        try:
            last = int(json.loads(state_path.read_text(encoding="utf-8")).get("last_version", 0))
        except (OSError, ValueError, TypeError):
            errors.append("STATE_CORRUPT")
    if isinstance(version, int):
        if version < last:
            errors.append(f"ROLLBACK version={version} last={last}")
        elif version == last:
            errors.append(f"DUPLICATE_VERSION version={version}")

    try:
        updated = datetime.fromisoformat(data["data_updated_at"])
        if updated.tzinfo is None:
            errors.append("TIMESTAMP_WITHOUT_TIMEZONE")
        age = (now - updated).total_seconds() / 86400
        metrics["age_days"] = round(age, 3)
        if age > max_age_days:
            errors.append(f"STALE_DATA age_days={age:.2f}")
        if age < -1 / 24:
            errors.append("FUTURE_DATA_UPDATED_AT")
    except (KeyError, TypeError, ValueError):
        errors.append("INVALID_DATA_UPDATED_AT")

    scope = data.get("scope")
    if scope not in {"TRIAL_MECHANICS", "P9_FULL_HISTORY"}:
        errors.append("UNKNOWN_SCOPE")
        return {"ok": False, "errors": errors, "metrics": metrics, "synthetic": True}

    actual_latest, per_ticker, membership_latest = _actual_dates(data)
    if actual_latest is None:
        errors.append("NO_OHLCV")
    if membership_latest is None:
        errors.append("NO_MEMBERSHIP")
    stated_latest = data.get("reported_latest_price_date")
    stated_mlatest = data.get("reported_membership_latest_date")
    if stated_latest and actual_latest and stated_latest != actual_latest.isoformat():
        errors.append("REPORTED_LATEST_MISMATCH")
    if stated_mlatest and membership_latest and stated_mlatest != membership_latest.isoformat():
        errors.append("REPORTED_MEMBERSHIP_MISMATCH")

    if scope == "P9_FULL_HISTORY":
        expected_start, expected_end = P9_START, P9_END
        if actual_latest != expected_end:
            errors.append(f"P9_END_MISMATCH actual={actual_latest} expected={expected_end}")
        first = min((date.fromisoformat(r["date"]) for r in data.get("ohlcv", [])), default=None)
        if first != expected_start:
            errors.append(f"P9_START_MISMATCH actual={first} expected={expected_start}")
        if membership_latest != expected_end:
            errors.append("P9_MEMBERSHIP_END_MISMATCH")
    else:
        try:
            trial_start = date.fromisoformat(data["trial_start_date"])
        except (KeyError, TypeError, ValueError):
            errors.append("TRIAL_START_MISSING")
            trial_start = None
        expected_end = expected_last_us_session(now)
        if actual_latest != expected_end:
            errors.append(f"LATEST_PRICE_DATE_LAG actual={actual_latest} expected={expected_end}")
        if trial_start:
            cutoff = trial_start.replace(year=trial_start.year - TRIAL_MAX_YEARS)
            first = min((date.fromisoformat(r["date"]) for r in data.get("ohlcv", [])), default=None)
            if first and first < cutoff:
                errors.append(f"TRIAL_HISTORY_TOO_LONG start={first} cutoff={cutoff}")
        if membership_latest != expected_end:
            errors.append("MEMBERSHIP_LATEST_LAG")

    # Per-ticker latest dates; missing non-core is handled by coverage, not a hard error.
    expected_set = set(data.get("expected_tickers", []))
    actual_set = set(per_ticker)
    for ticker in data.get("core_tickers", []):
        if ticker not in actual_set:
            errors.append(f"CORE_TICKER_MISSING {ticker}")
    for ticker in expected_set & actual_set:
        if per_ticker[ticker] != (expected_end if scope == "TRIAL_MECHANICS" else P9_END):
            errors.append(f"PER_TICKER_LATEST_LAG {ticker}")

    ticker_cov = len(expected_set & actual_set) / len(expected_set) if expected_set else 0
    metrics["ticker_coverage"] = round(ticker_cov, 4)
    if ticker_cov < ticker_gate:
        errors.append(f"TICKER_COVERAGE_LOW {ticker_cov:.4f}")

    seen = set()
    for r in data.get("ohlcv", []):
        k = (r.get("ticker"), r.get("date"))
        if k in seen:
            errors.append(f"DUPLICATE_OHLCV {k[0]} {k[1]}")
        seen.add(k)
        vals = [r.get(x) for x in ("open", "high", "low", "close", "volume")]
        if not all(_finite(v) for v in vals):
            errors.append(f"NON_FINITE_OHLCV {k[0]} {k[1]}")
            break
        o, h, l, c, v = [float(x) for x in vals]
        if v <= 0 or l <= 0 or o <= 0 or h <= 0 or c <= 0:
            errors.append(f"NON_POSITIVE_OHLCV {k[0]} {k[1]}")
            break
        if h < o or h < c or l > o or l > c or l > h:
            errors.append(f"BAD_OHLCV_RANGE {k[0]} {k[1]}")
            break

    asset_map = {}
    for row in data.get("assetid_map", []):
        asset_map[row["ticker"]] = row["assetid"]
    for r in data.get("ohlcv", []):
        if asset_map.get(r["ticker"]) != r.get("assetid"):
            errors.append(f"ASSETID_MISMATCH {r['ticker']}")
            break

    # Independent baseline is required; supplier data is not the denominator.
    baseline = data.get("expected_membership")
    if not baseline:
        errors.append("EXPECTED_MEMBERSHIP_NOT_VERIFIABLE")
        metrics["member_day_coverage"] = None
    else:
        base_keys = {(r["ticker"], r["date"]) for r in baseline if r.get("is_member") is True}
        actual_keys = {(r["ticker"], r["date"]) for r in data.get("membership", []) if r.get("is_member") is True}
        member_cov = len(base_keys & actual_keys) / len(base_keys) if base_keys else 0
        metrics["member_day_coverage"] = round(member_cov, 4)
        if member_cov < member_day_gate:
            errors.append(f"MEMBER_DAY_COVERAGE_LOW {member_cov:.4f}")
        # A False is valid; a missing row for an expected date/ticker is not.
        supplier_keys = {(r["ticker"], r["date"]) for r in data.get("membership", [])}
        baseline_all = {(r["ticker"], r["date"]) for r in baseline}
        missing_rows = baseline_all - supplier_keys
        if missing_rows:
            errors.append(f"MEMBERSHIP_RECORD_MISSING {len(missing_rows)}")
        # Daily completeness: every expected ticker must have a True/False row.
        daily = {}
        for r in data.get("membership", []):
            daily.setdefault(r["date"], set()).add(r["ticker"])
        incomplete = [d for d, got in daily.items() if got != expected_set]
        if incomplete:
            errors.append(f"MEMBERSHIP_DAY_INCOMPLETE {len(incomplete)}")
        metrics["min_daily_membership_completeness"] = 1.0 if not incomplete else 0.0

    return {"ok": not errors, "errors": errors, "metrics": metrics, "synthetic": True, "scope": scope}


def commit_bundle(
    data_path: Path,
    manifest_path: Path,
    key: str,
    *,
    state_path: Path,
    now: datetime | None = None,
    expected_scope: str | None = None,
) -> dict:
    """Validate, then atomically persist last accepted version.

    Production must replace this local state with a durable trusted store.
    """
    result = validate_bundle(
        data_path, manifest_path, key, now=now, state_path=state_path, expected_scope=expected_scope
    )
    if not result["ok"]:
        return {**result, "committed": False}
    version = result["metrics"].get("version")
    if not isinstance(version, int):
        return {**result, "ok": False, "errors": result["errors"] + ["INVALID_VERSION"], "committed": False}
    try:
        tmp_fd, tmp_name = tempfile.mkstemp(prefix=".p10-state-", dir=str(state_path.parent))
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump({"last_version": version}, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, state_path)
    except OSError:
        return {**result, "ok": False, "errors": result["errors"] + ["STATE_WRITE_FAILED"], "committed": False}
    return {**result, "committed": True}
