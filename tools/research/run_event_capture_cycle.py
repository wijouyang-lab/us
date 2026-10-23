"""Manual one-command event capture, archival, and as-of audit.

This research-only tool has no scheduler and never writes to production scanner
inputs. Each run saves unique immutable capture files, updates the logical
version archive, and emits a data-quality report at an explicit decision time.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import time
from typing import Any

from tools.research.official_event_rss_collector import OFFICIAL_FEEDS, OfficialRssCollector
from tools.research.pit_event_archive import append_archive_file
from tools.research.pit_event_eligibility import _parse_aware_timestamp
from tools.research.pit_event_research_pipeline import build_event_research_report
from tools.research.sec_event_collector import SecEventCollector, load_universe


DEFAULT_FEEDS = "bls_cpi,bls_employment,bea_releases,fed_all,fed_speeches"


def _dump(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False, default=str) + "\n"


def _write_new(path: Path, payload: Any) -> None:
    if path.exists():
        raise ValueError(f"refusing to overwrite existing capture file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(_dump(payload), encoding="utf-8")
    if path.exists():
        temporary.unlink(missing_ok=True)
        raise ValueError(f"capture path appeared during write; refusing overwrite: {path}")
    temporary.replace(path)


def _parse_max_age_days(raw: str) -> dict[str, timedelta]:
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"max-age config must be valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("max-age config must be a JSON object")
    result: dict[str, timedelta] = {}
    for kind, days in payload.items():
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError("max-age event type must be a non-empty string")
        if isinstance(days, bool) or not isinstance(days, (int, float)) or not math.isfinite(days) or days < 0:
            raise ValueError(f"max age for {kind} must be a finite non-negative number of days")
        result[kind] = timedelta(days=float(days))
    return result


def _parse_feeds(raw: str, sec_enabled: bool) -> list[str]:
    keys = list(dict.fromkeys(k.strip() for k in raw.split(",") if k.strip()))
    unknown = [k for k in keys if k not in OFFICIAL_FEEDS]
    if unknown:
        raise ValueError(f"unsupported official RSS feed(s): {', '.join(unknown)}")
    if not keys and not sec_enabled:
        raise ValueError("select at least one RSS feed or provide --sec-universe")
    return keys


def _validate_date(value: str, label: str) -> None:
    try:
        date.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{label} must use YYYY-MM-DD") from exc


def run_cycle(
    *,
    output_dir: str | Path,
    decision_at: str,
    feed_keys: list[str],
    sec_universe_path: str | Path | None = None,
    sec_start_date: str | None = None,
    sec_end_date: str | None = None,
    max_filings_per_company: int = 25,
    min_request_interval_seconds: float = 0.2,
    max_age_by_type: dict[str, timedelta] | None = None,
    feed_user_agent: str | None = None,
    sec_user_agent: str | None = None,
) -> dict[str, Any]:
    if _parse_aware_timestamp(decision_at) is None:
        raise ValueError("decision_at must be a timezone-aware ISO-8601 timestamp")
    if min_request_interval_seconds < 0.1:
        raise ValueError("request interval must be at least 0.1 seconds")
    if not feed_keys and not sec_universe_path:
        raise ValueError("select at least one RSS feed or provide --sec-universe")
    if sec_universe_path and (not sec_start_date or not sec_end_date):
        raise ValueError("--sec-start-date and --sec-end-date are required with --sec-universe")

    universe = load_universe(sec_universe_path) if sec_universe_path else []
    if sec_universe_path:
        _validate_date(str(sec_start_date), "sec_start_date")
        _validate_date(str(sec_end_date), "sec_end_date")
        if date.fromisoformat(str(sec_start_date)) > date.fromisoformat(str(sec_end_date)):
            raise ValueError("sec_start_date must not be after sec_end_date")

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    prefix = f"event_capture_{stamp}"
    events_path = root / f"{prefix}.events.json"
    metadata_path = root / f"{prefix}.metadata.json"
    audit_path = root / f"{prefix}.audit.json"
    archive_path = root / "event_archive.json"
    if any(path.exists() for path in (events_path, metadata_path, audit_path)):
        raise ValueError("capture filename collision; retry the command")

    cycle_started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    all_events: list[dict[str, Any]] = []
    source_reports: dict[str, Any] = {}
    configured_sources = len(feed_keys) + len(universe)
    successful_sources = 0

    if feed_keys:
        agent = feed_user_agent if feed_user_agent is not None else os.environ.get("OFFICIAL_FEED_USER_AGENT", "")
        rss = OfficialRssCollector(agent, min_request_interval_seconds=min_request_interval_seconds)
        result = rss.collect(feed_keys)
        source_reports["official_rss"] = result["metadata"]
        all_events.extend(result["events"])
        successful_sources += sum(
            report.get("status") == "ok"
            for report in result["metadata"]["feed_reports"]
        )

    if universe:
        agent = sec_user_agent if sec_user_agent is not None else os.environ.get("SEC_USER_AGENT", "")
        sec = SecEventCollector(
            agent,
            min_request_interval_seconds=max(0.15, min_request_interval_seconds),
        )
        company_reports: list[dict[str, Any]] = []
        for company in universe:
            try:
                result = sec.collect_company(
                    company["cik"],
                    company["ticker"],
                    start_date=str(sec_start_date),
                    end_date=str(sec_end_date),
                    max_filings=max_filings_per_company,
                )
                company_reports.append(result["metadata"])
                all_events.extend(result["events"])
                if result["metadata"].get("coverage_status") != "submissions_fetch_error":
                    successful_sources += 1
            except Exception as exc:
                company_reports.append({
                    "cik": company["cik"],
                    "ticker": company["ticker"],
                    "coverage_status": "submissions_fetch_error",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "event_count": 0,
                })
        source_reports["sec_edgar"] = {
            "company_count": len(universe),
            "company_reports": company_reports,
            "event_count": sum(int(row.get("event_count") or 0) for row in company_reports),
            "verified_header_timestamp_count": sum(
                int(row.get("verified_header_timestamp_count") or 0)
                for row in company_reports
            ),
            "partial_company_count": sum(
                row.get("coverage_status") in {"partial", "submissions_fetch_error"}
                for row in company_reports
            ),
            "research_only": True,
        }

    all_events.sort(key=lambda row: (
        row.get("published_at_utc") is None,
        str(row.get("published_at_utc") or ""),
        str(row.get("event_id") or ""),
        str(row.get("first_seen_at_utc") or ""),
    ))
    event_json = json.dumps(all_events, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    metadata = {
        "pipeline_version": "1.0",
        "cycle_started_at_utc": cycle_started,
        "cycle_completed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "decision_at_utc": decision_at,
        "requested_feed_keys": feed_keys,
        "sec_universe": universe,
        "event_count": len(all_events),
        "event_snapshot_sha256": sha256(event_json.encode("utf-8")).hexdigest(),
        "source_reports": source_reports,
        "successful_source_count": successful_sources,
        "configured_source_count": configured_sources,
        "research_only": True,
        "production_scanner_modified": False,
        "scheduled_workflow_created": False,
    }
    _write_new(events_path, all_events)
    _write_new(metadata_path, metadata)

    archive_summary = append_archive_file(events_path, archive_path)
    archive_rows = json.loads(archive_path.read_text(encoding="utf-8"))
    audit = build_event_research_report(
        archive_rows,
        decision_at,
        max_age_by_type=max_age_by_type,
    )
    source_collection_coverage: list[dict[str, Any]] = []
    for feed_report in source_reports.get("official_rss", {}).get("feed_reports", []):
        feed_key = str(feed_report.get("feed_key") or "")
        feed_config = OFFICIAL_FEEDS.get(feed_key, {})
        source_collection_coverage.append({
            "source_kind": "official_rss",
            "feed_key": feed_key or None,
            "source": feed_config.get("source"),
            "status": str(feed_report.get("status") or "status_missing"),
            "event_count": int(feed_report.get("event_count") or 0),
            "item_count": feed_report.get("item_count"),
            "error_type": feed_report.get("error_type"),
        })
    sec_report = source_reports.get("sec_edgar", {})
    for company_report in sec_report.get("company_reports", []):
        source_collection_coverage.append({
            "source_kind": "sec_edgar",
            "ticker": company_report.get("ticker"),
            "cik": company_report.get("cik"),
            "status": str(company_report.get("coverage_status") or "status_missing"),
            "event_count": int(company_report.get("event_count") or 0),
            "error_type": company_report.get("error_type"),
        })
    source_collection_coverage.sort(key=lambda row: (
        str(row.get("source_kind") or ""),
        str(row.get("feed_key") or row.get("ticker") or ""),
    ))

    audit["capture_cycle"] = {
        "events_file": str(events_path),
        "metadata_file": str(metadata_path),
        "archive_file": str(archive_path),
        "archive_update": archive_summary,
        "successful_source_count": successful_sources,
        "configured_source_count": configured_sources,
        "all_sources_failed": successful_sources == 0,
        "source_collection_coverage": source_collection_coverage,
    }
    _write_new(audit_path, audit)
    return {
        "events_path": str(events_path),
        "metadata_path": str(metadata_path),
        "archive_path": str(archive_path),
        "audit_path": str(audit_path),
        "event_count": len(all_events),
        "successful_source_count": successful_sources,
        "configured_source_count": configured_sources,
        "all_sources_failed": successful_sources == 0,
        "audit_status": audit["coverage_audit"]["audit_status"],
        "report": audit,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--decision-at", required=True, help="Timezone-aware ISO-8601 decision timestamp")
    parser.add_argument("--feeds", default=DEFAULT_FEEDS, help="Comma-separated official feed keys; empty for SEC-only")
    parser.add_argument("--sec-universe", help="Optional JSON array containing explicit CIK/ticker pairs")
    parser.add_argument("--sec-start-date")
    parser.add_argument("--sec-end-date")
    parser.add_argument("--max-filings-per-company", type=int, default=25)
    parser.add_argument("--min-request-interval-seconds", type=float, default=0.2)
    parser.add_argument("--max-age-days-by-type", default="{}", help='Optional JSON freshness config such as {"macro_release":2}')
    args = parser.parse_args(argv)
    try:
        feeds = _parse_feeds(args.feeds, bool(args.sec_universe))
        freshness = _parse_max_age_days(args.max_age_days_by_type)
        result = run_cycle(
            output_dir=args.output_dir,
            decision_at=args.decision_at,
            feed_keys=feeds,
            sec_universe_path=args.sec_universe,
            sec_start_date=args.sec_start_date,
            sec_end_date=args.sec_end_date,
            max_filings_per_company=args.max_filings_per_company,
            min_request_interval_seconds=args.min_request_interval_seconds,
            max_age_by_type=freshness,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print(f"Captured events: {result['event_count']}")
    print(f"Snapshot: {result['events_path']}")
    print(f"Metadata: {result['metadata_path']}")
    print(f"Archive: {result['archive_path']}")
    print(f"Audit: {result['audit_path']} ({result['audit_status']})")
    return 1 if result["all_sources_failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
