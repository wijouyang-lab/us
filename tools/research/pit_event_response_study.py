"""Descriptive, point-in-time event response study over frozen event and price snapshots.

This module reports forward price outcomes after the collector first observed an
event. It does not infer sentiment, produce trading signals, or claim causal
alpha. Price bars must be supplied as CSV with date,ticker,open,close columns.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
import csv
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
MARKET_WIDE_TYPES = {"macro_release", "central_bank", "policy", "geopolitical"}


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        default=str, allow_nan=False,
    )


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _event_version_id(event: Mapping[str, Any]) -> str:
    row = dict(event)
    row.pop("first_seen_at_utc", None)
    row.pop("event_version_id", None)
    return sha256(_canonical_json(row).encode("utf-8")).hexdigest()


def _parse_horizons(raw: Iterable[int]) -> list[int]:
    horizons = sorted(set(raw))
    if not horizons or any(isinstance(h, bool) or not isinstance(h, int) or h < 1 or h > 252 for h in horizons):
        raise ValueError("horizons must contain whole trading-session counts between 1 and 252")
    return horizons


def parse_max_age_days(raw: str | Mapping[str, Any] | None) -> dict[str, timedelta]:
    if raw is None or raw == "":
        return {}
    try:
        payload = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ValueError("max-age config must be a JSON object") from exc
    if not isinstance(payload, dict):
        raise ValueError("max-age config must be a JSON object")
    result: dict[str, timedelta] = {}
    for event_type, days in payload.items():
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError("event type in max-age config must be a non-empty string")
        if isinstance(days, bool) or not isinstance(days, (int, float)) or not math.isfinite(days) or days < 0 or days > 365000:
            raise ValueError(f"max age for {event_type} must be finite and between 0 and 365000 days")
        result[event_type] = timedelta(days=float(days))
    return result


def _load_events(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read event JSON: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid event JSON: {exc}") from exc
    if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
        raise ValueError("event JSON must be an array of objects")
    return payload


def _load_price_bars(
    path: str | Path,
    study_end_date: date,
    *,
    price_basis: str = "auto",
) -> tuple[dict[str, list[dict[str, Any]]], str, dict[str, Any]]:
    """Load one consistent price basis; prefer adjusted prices when available.

    The adjusted route accepts either Adj Open + Adj Close, or raw Open/Close
    plus Adj Close, in which case adjusted Open is derived using the same-day
    Adj Close / Close factor. It never mixes adjusted and raw prices by row.
    """
    if price_basis not in {"auto", "adjusted", "raw"}:
        raise ValueError("price_basis must be auto, adjusted, or raw")
    source = Path(path)
    try:
        raw_bytes = source.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read price CSV: {exc}") from exc
    price_hash = sha256(raw_bytes).hexdigest()
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("price CSV must be UTF-8 text") from exc
    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        raise ValueError("price CSV is missing a header row")
    fields = {name.strip().lower(): name for name in reader.fieldnames if name}
    if not {"date", "ticker"}.issubset(fields):
        raise ValueError("price CSV requires date,ticker columns")

    raw_open = fields.get("open")
    raw_close = fields.get("close")
    adj_open = fields.get("adj open") or fields.get("adjusted open")
    adj_close = fields.get("adj close") or fields.get("adjusted close")

    if price_basis == "raw":
        if not raw_open or not raw_close:
            raise ValueError("raw price basis requires Open and Close columns")
        selected_basis = "raw_ohlc"
    elif price_basis == "adjusted":
        if adj_open and adj_close:
            selected_basis = "adjusted_ohlc"
        elif adj_close and raw_open and raw_close:
            selected_basis = "adjusted_ohlc_derived_open"
        else:
            raise ValueError(
                "adjusted price basis requires Adj Open + Adj Close, or raw Open + raw Close + Adj Close"
            )
    else:
        has_adjusted = bool(adj_open or adj_close)
        if not has_adjusted:
            if not raw_open or not raw_close:
                raise ValueError("price CSV requires Open and Close columns")
            selected_basis = "raw_ohlc"
        elif adj_open and adj_close:
            selected_basis = "adjusted_ohlc"
        elif adj_close and raw_open and raw_close:
            selected_basis = "adjusted_ohlc_derived_open"
        else:
            raise ValueError(
                "partial adjusted-price columns are present but cannot form a consistent adjusted basis"
            )

    if selected_basis == "adjusted_ohlc":
        open_field, close_field = adj_open, adj_close
    elif selected_basis == "adjusted_ohlc_derived_open":
        open_field, close_field = raw_open, adj_close
    else:
        open_field, close_field = raw_open, raw_close

    rows: dict[str, dict[date, dict[str, Any]]] = defaultdict(dict)
    seen_keys: set[tuple[str, date]] = set()
    input_rows = 0
    used_rows = 0
    skipped_missing_price_rows = 0
    for line_num, raw in enumerate(reader, start=2):
        if not raw or not any(str(value or "").strip() for value in raw.values()):
            continue
        input_rows += 1
        date_text = str(raw.get(fields["date"]) or "").strip()
        ticker = str(raw.get(fields["ticker"]) or "").strip().upper().replace("$", "")
        if not ticker:
            raise ValueError(f"missing ticker at CSV line {line_num}")
        try:
            session_date = date.fromisoformat(date_text[:10])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid date at CSV line {line_num}") from exc

        key = (ticker, session_date)
        if key in seen_keys:
            raise ValueError(f"duplicate ticker/date row for {ticker} on {session_date.isoformat()}")
        seen_keys.add(key)
        if session_date > study_end_date:
            continue

        try:
            if selected_basis == "adjusted_ohlc_derived_open":
                raw_open_value = float(str(raw.get(raw_open) or "").strip()) if raw_open else None
                raw_close_value = float(str(raw.get(raw_close) or "").strip()) if raw_close else None
            else:
                raw_open_value = None
                raw_close_value = None
            open_text = str(raw.get(open_field) or "").strip() if open_field else ""
            close_text = str(raw.get(close_field) or "").strip() if close_field else ""
            open_price = float(open_text) if open_text else math.nan
            close_price = float(close_text) if close_text else math.nan
        except (TypeError, ValueError):
            skipped_missing_price_rows += 1
            continue

        if selected_basis == "adjusted_ohlc_derived_open":
            if not math.isfinite(raw_open_value or math.nan) or not math.isfinite(raw_close_value or math.nan) or raw_close_value is None or raw_close_value <= 0:
                skipped_missing_price_rows += 1
                continue
            open_price = raw_open_value * close_price / raw_close_value

        if (
            not math.isfinite(open_price) or not math.isfinite(close_price)
            or open_price <= 0 or close_price <= 0
        ):
            skipped_missing_price_rows += 1
            continue

        rows[ticker][session_date] = {
            "date": session_date,
            "open": open_price,
            "close": close_price,
        }
        used_rows += 1

    output = {
        ticker: [day_map[d] for d in sorted(day_map)]
        for ticker, day_map in rows.items()
    }
    quality = {
        "selected_price_basis": selected_basis,
        "input_row_count": input_rows,
        "usable_price_row_count": used_rows,
        "skipped_rows_missing_or_invalid_selected_basis": skipped_missing_price_rows,
        "adjusted_open_derivation": (
            "raw_open * adj_close / raw_close"
            if selected_basis == "adjusted_ohlc_derived_open" else None
        ),
    }
    return output, price_hash, quality

def _first_observed_versions(
    events: Iterable[Mapping[str, Any]],
    *,
    study_end_date: date,
    max_age_by_type: Mapping[str, timedelta],
    skip_reasons: Counter[str],
) -> list[dict[str, Any]]:
    """Choose the earliest source version before checking eligibility.

    Filtering invalid versions first could allow later corrected content to
    replace an unavailable/missing-timestamp first version, introducing leakage.
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in events:
        event = dict(source)
        event_id = str(event.get("event_id") or "").strip()
        if not event_id:
            skip_reasons["event_id_missing"] += 1
            continue
        if str(event.get("availability_status") or "") == "fetch_error":
            skip_reasons["availability_fetch_error"] += 1
            continue
        grouped[event_id].append(event)

    selected: list[dict[str, Any]] = []
    for event_id, versions in grouped.items():
        parsed_rows: list[tuple[datetime, str, dict[str, Any]]] = []
        bad_first_seen = False
        for event in versions:
            first_seen = _parse_timestamp(event.get("first_seen_at_utc"))
            if first_seen is None:
                bad_first_seen = True
                break
            version_id = _event_version_id(event)
            supplied_version = str(event.get("event_version_id") or "").strip()
            if supplied_version and supplied_version != version_id:
                skip_reasons["event_version_hash_mismatch"] += 1
                event["_pit_invalid_version_hash"] = True
            event["event_version_id"] = supplied_version or version_id
            parsed_rows.append((first_seen, event["event_version_id"], event))

        if bad_first_seen:
            skip_reasons["first_seen_timestamp_missing_or_invalid"] += 1
            continue
        parsed_rows.sort(key=lambda row: (row[0], row[1]))
        earliest_time = parsed_rows[0][0]
        earliest = [row for row in parsed_rows if row[0] == earliest_time]
        if len({row[1] for row in earliest}) > 1:
            skip_reasons["ambiguous_versions_same_first_seen"] += 1
            continue
        event = earliest[0][2]
        if event.get("_pit_invalid_version_hash"):
            continue
        if str(event.get("availability_status") or "") != "available":
            skip_reasons[f"availability_{event.get('availability_status') or 'status_missing'}"] += 1
            continue

        first_seen = earliest[0][0]
        published = _parse_timestamp(event.get("published_at_utc"))
        if published is None:
            skip_reasons["published_timestamp_missing_or_invalid"] += 1
            continue
        if published > first_seen:
            skip_reasons["published_after_first_seen"] += 1
            continue
        if first_seen.astimezone(NY).date() > study_end_date:
            skip_reasons["first_seen_after_study_end"] += 1
            continue

        updated_raw = event.get("updated_at_utc")
        if updated_raw is not None:
            updated = _parse_timestamp(updated_raw)
            update_seen = _parse_timestamp(event.get("update_first_seen_at_utc"))
            if updated is None or update_seen is None or updated > first_seen or update_seen > first_seen or update_seen < updated:
                skip_reasons["unverifiable_revision_at_first_observation"] += 1
                continue

        event_type = str(event.get("event_type") or "unknown")
        max_age = max_age_by_type.get(event_type)
        if max_age is not None and first_seen - published > max_age:
            skip_reasons["stale_event_at_first_observation"] += 1
            continue

        event.pop("_pit_invalid_version_hash", None)
        selected.append(event)
        skip_reasons["later_revision_excluded"] += max(0, len(versions) - 1)

    selected.sort(key=lambda row: (
        str(row.get("first_seen_at_utc") or ""),
        str(row.get("event_id") or ""),
        str(row.get("event_version_id") or ""),
    ))
    return selected


def _targets_for_event(event: Mapping[str, Any], skip_reasons: Counter[str]) -> list[str]:
    kind = str(event.get("event_type") or "unknown")
    if kind in MARKET_WIDE_TYPES:
        return ["SPY"]

    # A symbol-scoped aggregator feed is only a query scope, not proof that the
    # story itself concerns the queried company. Require an explicit verification
    # status before using these company-level events in response studies.
    source = str(event.get("source") or "").strip().lower()
    mapping_status = str(event.get("ticker_mapping_status") or "").strip().lower()
    verified_mapping_statuses = {"verified", "content_verified", "human_reviewed"}
    is_aggregator_company_event = (
        kind in {"company_news", "earnings"}
        and (
            source == "yahoo_finance_rss"
            or str(event.get("source_quality") or "").strip().lower() == "aggregator"
        )
    )
    has_unverified_explicit_mapping = bool(mapping_status) and mapping_status not in verified_mapping_statuses
    if kind in {"company_news", "earnings"} and (
        (is_aggregator_company_event and mapping_status not in verified_mapping_statuses)
        or has_unverified_explicit_mapping
    ):
        skip_reasons["company_event_ticker_mapping_unverified"] += 1
        return []

    values = event.get("tickers")
    tickers = sorted({
        str(value).strip().upper().replace("$", "")
        for value in values
        if str(value).strip()
    }) if isinstance(values, list) else []
    if not tickers:
        skip_reasons["company_event_ticker_mapping_missing"] += 1
    return tickers


def _aggregate(observations: list[dict[str, Any]], horizons: list[int], cost_bps: float) -> list[dict[str, Any]]:
    groups: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        for horizon in horizons:
            value = row.get(f"gross_return_{horizon}s")
            if value is not None:
                groups[(str(row["event_type"]), horizon)].append(row)
    output: list[dict[str, Any]] = []
    for (event_type, horizon), rows in sorted(groups.items()):
        returns = [float(row[f"gross_return_{horizon}s"]) for row in rows]
        net = [value - cost_bps / 10000.0 for value in returns]
        output.append({
            "event_type": event_type,
            "horizon_sessions": horizon,
            "observation_count": len(rows),
            "distinct_event_count": len({row["event_id"] for row in rows}),
            "distinct_ticker_count": len({row["ticker"] for row in rows}),
            "mean_gross_return": statistics.mean(returns),
            "median_gross_return": statistics.median(returns),
            "gross_win_rate": sum(value > 0 for value in returns) / len(returns),
            "mean_net_return_after_assumed_cost": statistics.mean(net),
            "median_net_return_after_assumed_cost": statistics.median(net),
            "assumed_round_trip_cost_bps": cost_bps,
            "interpretation": "descriptive only; observations can overlap and are not a trading signal",
        })
    return output


def run_event_response_study(
    events: Iterable[Mapping[str, Any]],
    price_bars: Mapping[str, list[Mapping[str, Any]]],
    *,
    study_end_date: str | date,
    horizons: Iterable[int] = (1, 5, 10),
    round_trip_cost_bps: float = 0.0,
    max_age_by_type: Mapping[str, timedelta] | None = None,
    event_snapshot_sha256: str | None = None,
    price_snapshot_sha256: str | None = None,
    price_quality: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Report price outcomes after first observed versions; never generate signals."""
    if isinstance(study_end_date, str):
        try:
            end_date = date.fromisoformat(study_end_date)
        except ValueError as exc:
            raise ValueError("study_end_date must use YYYY-MM-DD") from exc
    elif isinstance(study_end_date, date):
        end_date = study_end_date
    else:
        raise ValueError("study_end_date must use YYYY-MM-DD")
    horizon_list = _parse_horizons(horizons)
    if not math.isfinite(round_trip_cost_bps) or round_trip_cost_bps < 0:
        raise ValueError("round_trip_cost_bps must be finite and non-negative")

    normalized_bars: dict[str, list[dict[str, Any]]] = {}
    date_arrays: dict[str, list[date]] = {}
    for raw_ticker, raw_rows in price_bars.items():
        ticker = str(raw_ticker).strip().upper().replace("$", "")
        if not ticker:
            continue
        sorted_rows = sorted(
            (dict(row) for row in raw_rows if row.get("date") <= end_date),
            key=lambda row: row["date"],
        )
        dates = [row["date"] for row in sorted_rows]
        if len(dates) != len(set(dates)):
            raise ValueError(f"duplicate price sessions for ticker {ticker}")
        for row in sorted_rows:
            for field in ("open", "close"):
                value = float(row[field])
                if not math.isfinite(value) or value <= 0:
                    raise ValueError(f"invalid {field} price for {ticker} on {row['date']}")
        normalized_bars[ticker] = sorted_rows
        date_arrays[ticker] = dates

    skip_reasons: Counter[str] = Counter()
    source_events = list(events)
    selected_events = _first_observed_versions(
        source_events,
        study_end_date=end_date,
        max_age_by_type=max_age_by_type or {},
        skip_reasons=skip_reasons,
    )
    observations: list[dict[str, Any]] = []

    for event in selected_events:
        event_id = str(event["event_id"])
        kind = str(event.get("event_type") or "unknown")
        first_seen = _parse_timestamp(event.get("first_seen_at_utc"))
        published = _parse_timestamp(event.get("published_at_utc"))
        if first_seen is None or published is None:
            continue
        local_seen = first_seen.astimezone(NY)
        targets = _targets_for_event(event, skip_reasons)
        for ticker in targets:
            if ticker not in normalized_bars or not normalized_bars[ticker]:
                skip_reasons["price_series_missing_for_ticker"] += 1
                continue
            bars = normalized_bars[ticker]
            dates = date_arrays[ticker]
            if local_seen.time().replace(tzinfo=None) < time(9, 30):
                entry_idx = bisect_left(dates, local_seen.date())
            else:
                entry_idx = bisect_right(dates, local_seen.date())
            if entry_idx >= len(bars):
                skip_reasons["no_price_session_after_observation"] += 1
                continue

            entry = bars[entry_idx]
            observation: dict[str, Any] = {
                "event_id": event_id,
                "event_version_id": str(event.get("event_version_id") or ""),
                "event_type": kind,
                "source": str(event.get("source") or ""),
                "ticker": ticker,
                "ticker_mapping_method": str(event.get("ticker_mapping_method") or ""),
                "ticker_mapping_status": str(event.get("ticker_mapping_status") or ""),
                "ticker_mapping_confidence": str(event.get("ticker_mapping_confidence") or ""),
                "published_at_utc": str(event.get("published_at_utc") or ""),
                "first_seen_at_utc": str(event.get("first_seen_at_utc") or ""),
                "source_delay_minutes": (first_seen - published).total_seconds() / 60.0,
                "entry_date": entry["date"].isoformat(),
                "entry_open": float(entry["open"]),
            }
            has_any_return = False
            for horizon in horizon_list:
                exit_idx = entry_idx + horizon - 1
                if exit_idx >= len(bars):
                    observation[f"exit_date_{horizon}s"] = None
                    observation[f"gross_return_{horizon}s"] = None
                    observation[f"net_return_{horizon}s"] = None
                    skip_reasons[f"insufficient_price_horizon_{horizon}s"] += 1
                    continue
                exit_row = bars[exit_idx]
                gross = float(exit_row["close"]) / float(entry["open"]) - 1.0
                observation[f"exit_date_{horizon}s"] = exit_row["date"].isoformat()
                observation[f"gross_return_{horizon}s"] = gross
                observation[f"net_return_{horizon}s"] = gross - round_trip_cost_bps / 10000.0
                has_any_return = True
            if has_any_return:
                observations.append(observation)
            else:
                skip_reasons["no_complete_forward_horizon"] += 1

    observations.sort(key=lambda row: (
        row["first_seen_at_utc"], row["event_id"], row["ticker"]
    ))
    aggregates = _aggregate(observations, horizon_list, round_trip_cost_bps)
    return {
        "study_version": "1.0",
        "study_end_date": end_date.isoformat(),
        "horizons_sessions": horizon_list,
        "round_trip_cost_bps": round_trip_cost_bps,
        "input_event_record_count": len(source_events),
        "first_observed_event_count": len(selected_events),
        "observation_count": len(observations),
        "skip_reason_counts": dict(sorted(skip_reasons.items())),
        "event_snapshot_sha256": event_snapshot_sha256,
        "price_snapshot_sha256": price_snapshot_sha256,
        "price_quality": dict(price_quality or {"selected_price_basis": "caller_supplied_ohlc"}),
        "observations": observations,
        "aggregates_by_event_type": aggregates,
        "methodology": {
            "entry_rule": "before 09:30 America/New_York may enter at that session open; otherwise use the next available session open",
            "exit_rule": "horizon N exits at the close of the entry session plus N-1 trading sessions",
            "version_rule": "only the earliest version per event ID is used; later revisions are excluded",
            "market_wide_proxy": "macro_release, central_bank, policy, and geopolitical events map to SPY",
            "mapping_rule": "company_news and earnings require explicit ticker mapping; ticker-query aggregator results are skipped unless the company mapping is explicitly verified",
            "cost_rule": "assumed round-trip cost is subtracted from each forward return; set by the caller",
            "known_limitations": [
                "This measures returns after the collector first observed an event, not necessarily after the event first became public.",
                "Publisher timestamps are metadata and can differ from the actual first-public-availability time.",
                "No validated positive/negative sentiment is inferred; aggregates are descriptive and not directional alpha.",
                "Windows may overlap; significance and causal alpha are not estimated.",
                "Price adjustments and source coverage are only as good as the caller-supplied CSV.",
                "Ticker-specific aggregator RSS queries can return unrelated headlines; query scope is not treated as verified company mapping.",
            ],
        },
        "research_only": True,
        "trading_signal_generated": False,
    }


def write_observations_csv(path: str | Path, report: Mapping[str, Any]) -> None:
    output = Path(path)
    if output.exists():
        raise ValueError(f"refusing to overwrite existing observations file: {output}")
    horizons = list(report["horizons_sessions"])
    fields = [
        "event_id", "event_version_id", "event_type", "source", "ticker",
        "published_at_utc", "first_seen_at_utc", "source_delay_minutes",
        "entry_date", "entry_open",
    ]
    for horizon in horizons:
        fields.extend([f"exit_date_{horizon}s", f"gross_return_{horizon}s", f"net_return_{horizon}s"])
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(report["observations"])
    if output.exists():
        temporary.unlink(missing_ok=True)
        raise ValueError(f"observations path appeared during write; refusing overwrite: {output}")
    temporary.replace(output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", required=True, help="Normalized event JSON array or version archive")
    parser.add_argument("--prices-csv", required=True, help="CSV with date,ticker,open,close columns; adjusted columns are preferred when available")
    parser.add_argument("--price-basis", choices=("auto", "adjusted", "raw"), default="auto", help="auto prefers adjusted OHLC, deriving Adj Open from Adj Close if needed")
    parser.add_argument("--study-end-date", required=True, help="Last trading session permitted in study (YYYY-MM-DD)")
    parser.add_argument("--report", required=True, help="New JSON report path")
    parser.add_argument("--observations-csv", help="Optional new CSV output for event-level observations")
    parser.add_argument("--horizons", default="1,5,10")
    parser.add_argument("--round-trip-cost-bps", type=float, default=0.0)
    parser.add_argument("--max-age-days-by-type", default="{}")
    args = parser.parse_args(argv)

    try:
        study_end_date = date.fromisoformat(args.study_end_date)
        event_rows = _load_events(args.events)
        bars, price_hash, price_quality = _load_price_bars(
            args.prices_csv, study_end_date, price_basis=args.price_basis
        )
        horizons = [int(value.strip()) for value in args.horizons.split(",") if value.strip()]
        freshness = parse_max_age_days(args.max_age_days_by_type)
        report_path = Path(args.report)
        if report_path.exists():
            raise ValueError(f"refusing to overwrite existing report: {report_path}")
        observations_path = Path(args.observations_csv) if args.observations_csv else None
        if observations_path and observations_path.exists():
            raise ValueError(f"refusing to overwrite existing observations file: {observations_path}")
        event_hash = sha256(Path(args.events).read_bytes()).hexdigest()
        report = run_event_response_study(
            event_rows,
            bars,
            study_end_date=study_end_date,
            horizons=horizons,
            round_trip_cost_bps=args.round_trip_cost_bps,
            max_age_by_type=freshness,
            event_snapshot_sha256=event_hash,
            price_snapshot_sha256=price_hash,
            price_quality=price_quality,
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = report_path.with_name(report_path.name + ".tmp")
        temporary.write_text(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        if report_path.exists():
            temporary.unlink(missing_ok=True)
            raise ValueError(f"report path appeared during write; refusing overwrite: {report_path}")
        temporary.replace(report_path)
        if observations_path:
            write_observations_csv(observations_path, report)
    except (OSError, ValueError, OverflowError) as exc:
        parser.error(str(exc))

    print(f"Event-response observations: {report['observation_count']}")
    print(f"Report: {report_path}")
    print(f"Status: {'ready_for_descriptive_review' if report['observation_count'] else 'no_eligible_price_windows'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
