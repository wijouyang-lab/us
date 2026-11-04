#!/usr/bin/env python3
"""Export only field-audited P4.5 dividend events for the public dashboard.

Reads existing research JSON. No SEC access, no SEC_USER_AGENT, no strategy code.
The field-level audit is the authority for values; the aggregate event file must
match it exactly or the exporter fails closed and preserves the existing snapshot.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

SRC_EVENTS = Path("data/research/dividend_events_targeted_p45.json")
SRC_AUDIT = Path("data/research/dividend_event_field_audit_p45.json")
SRC_EXCL = Path("data/research/dividend_event_exclusions_p45.json")
OUT = Path("dashboard/data/dividend_quality.json")
SOURCE_SHA = "6c131858bb2eef4ff9fd219caf3171813c217e6e"
VERIFICATION_URL = "https://github.com/wijouyang-lab/us/actions/runs/41819727044"

NOT_DISCLOSED = "NOT_DISCLOSED_IN_FILING"
AUDIT_FIELD_MAP = {
    "announcement_date": ("announcement", {"VERIFIED"}),
    "declared_per_share": ("declared_per_share", {"VERIFIED"}),
    "security_type": ("security_type", {"VERIFIED"}),
    "frequency": ("frequency", {"VERIFIED"}),
    "record_date": ("record_date", {"VERIFIED"}),
    "payment_date": ("payment_date", {"VERIFIED"}),
    "increase_per_share": ("increase_per_share", {"VERIFIED"}),
    "increase_pct": ("increase_pct", {"VERIFIED"}),
    "previous_per_share": ("previous_per_share", {"VERIFIED", NOT_DISCLOSED}),
    "ex_date": ("ex_date", {NOT_DISCLOSED}),
}


def _safe_url(url: str) -> bool:
    try:
        parsed = urlsplit(str(url or ""))
        return (
            parsed.scheme.lower() == "https"
            and parsed.hostname == "www.sec.gov"
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
            and parsed.path.startswith("/Archives/edgar/data/")
        )
    except (TypeError, ValueError):
        return False


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _url_matches_filing(url, cik, accession):
    try:
        cik_num = int(cik)
    except (TypeError, ValueError):
        return False
    parsed = urlsplit(str(url or ""))
    return (
        f"/{cik_num}/" in parsed.path
        and accession.replace("-", "") in parsed.path
        and parsed.path.startswith("/Archives/edgar/data/")
    )


def _manifest_has_file(manifest, ticker, accession, filename, sha256):
    for item in manifest:
        path = str(item.get("file") or "").replace("\\", "/")
        parts = path.split("/")
        if (
            item.get("sha256") == sha256
            and parts[-1] == filename
            and ticker in parts
            and accession in parts
        ):
            return True
    return False


def _audited_fields(event, audit_event):
    fields = audit_event.get("fields", {})
    values = {}
    statuses = {}
    for output_key, (audit_key, allowed_statuses) in AUDIT_FIELD_MAP.items():
        field = fields.get(audit_key)
        if not isinstance(field, dict):
            raise ValueError(f"{event.get('ticker')}: missing field audit for {audit_key}")
        status = field.get("status")
        if status not in allowed_statuses:
            raise ValueError(
                f"{event.get('ticker')}: unacceptable audit status for {audit_key}: {status}"
            )
        normalized = field.get("normalized")
        if status == NOT_DISCLOSED and normalized is not None:
            raise ValueError(
                f"{event.get('ticker')}: {audit_key} is NOT_DISCLOSED but normalized is not null"
            )
        if event.get(output_key) != normalized:
            raise ValueError(
                f"{event.get('ticker')}: {output_key} does not match field audit "
                f"({event.get(output_key)!r} != {normalized!r})"
            )
        values[output_key] = normalized
        statuses[output_key] = status

    for output_key in ("previous_per_share", "ex_date"):
        status_key = output_key + "_status"
        if event.get(status_key) != statuses[output_key]:
            raise ValueError(
                f"{event.get('ticker')}: {status_key} does not match field audit"
            )
    return values, statuses, fields


def _verified_sources(event, audit_hash_manifest, ticker, accession):
    role_specs = {
        "EXHIBIT": ("EXHIBIT", "SEC Exhibit 99.1"),
        "PRIMARY": ("PRIMARY", "SEC Form 8-K"),
    }
    candidates = event.get("sources", [])
    if not isinstance(candidates, list):
        raise ValueError(f"{event.get('ticker')}: sources must be a list")

    result = []
    seen_roles = set()
    for source in candidates:
        if not isinstance(source, dict):
            continue
        role = source.get("role")
        if role not in role_specs or role in seen_roles:
            continue
        expected_doc_role, expected_type = role_specs[role]
        url = source.get("url")
        sha = source.get("sha256")
        filename = str(source.get("filename") or "")
        matching_manifest_file = _manifest_has_file(
            audit_hash_manifest, ticker, accession, filename, sha
        )
        if (
            not _safe_url(url)
            or not _url_matches_filing(url, event.get("cik"), accession)
            or not matching_manifest_file
            or source.get("source_type") != expected_type
        ):
            continue
        seen_roles.add(role)
        result.append({
            "role": role,
            "source_type": expected_type,
            "url": url,
            "filename": source.get("filename"),
            "sha256": sha,
        })

    if seen_roles != set(role_specs):
        raise ValueError(f"{event.get('ticker')}: both audited EXHIBIT and PRIMARY sources are required")
    return result


def build(events_doc, audit_doc, excl_doc):
    audit_hash_manifest = [
        item for item in audit_doc.get("hashes", [])
        if isinstance(item, dict) and item.get("sha256") and item.get("file")
    ]
    audit_by_ticker = {
        item["ticker"]: item
        for item in audit_doc.get("events", [])
        if isinstance(item, dict) and item.get("ticker")
    }
    events = []
    for event in events_doc.get("events", []):
        ticker = event.get("ticker")
        if event.get("verification_status") != "VERIFIED":
            continue
        audit_event = audit_by_ticker.get(ticker)
        if not audit_event:
            raise ValueError(f"{ticker}: verified event has no field audit")
        if audit_event.get("event_status") != "VERIFIED":
            raise ValueError(f"{ticker}: verified event has non-verified field audit")
        if event.get("accession_number") != audit_event.get("accession"):
            raise ValueError(f"{ticker}: accession number does not match field audit")

        values, statuses, audit_fields = _audited_fields(event, audit_event)
        sources = _verified_sources(event, audit_hash_manifest, ticker, audit_event["accession"])
        exhibit = next(source for source in sources if source["role"] == "EXHIBIT")

        events.append({
            "ticker": ticker,
            "event_type": event.get("event_type"),
            "security_type": values["security_type"],
            "declared_per_share": values["declared_per_share"],
            "previous_per_share": values["previous_per_share"],
            "previous_per_share_status": statuses["previous_per_share"],
            "increase_per_share": values["increase_per_share"],
            "increase_pct": values["increase_pct"],
            "announcement_date": values["announcement_date"],
            "record_date": values["record_date"],
            "payment_date": values["payment_date"],
            "ex_date": values["ex_date"],
            "ex_date_status": statuses["ex_date"],
            "verification_status": "VERIFIED",
            "sources": sources,
            "source_url": exhibit["url"],
            "source_type": exhibit["source_type"],
            "document_role": "EXHIBIT",
            "accession_number": audit_event["accession"],
            "evidence_sha256": exhibit["sha256"],
        })

    exclusions = []
    for item in excl_doc.get("exclusions", []):
        url = item.get("source_url")
        sha = item.get("evidence_sha256")
        ticker = str(item.get("ticker") or "")
        accession = str(item.get("accession_number") or "")
        raw_context = str(item.get("raw_context") or "")
        declared = item.get("declared_per_share")
        if not _safe_url(url):
            raise ValueError(f"{ticker}: preferred exclusion has an unsafe SEC URL")
        if not _url_matches_filing(url, item.get("cik"), accession):
            raise ValueError(f"{ticker}: preferred exclusion URL does not match its filing")
        if item.get("source_type") != "SEC Exhibit 99.1":
            raise ValueError(f"{ticker}: preferred exclusion source type is not SEC Exhibit 99.1")
        filename = urlsplit(url).path.rsplit("/", 1)[-1]
        if not _manifest_has_file(audit_hash_manifest, ticker, accession, filename, sha):
            raise ValueError(f"{ticker}: preferred exclusion hash does not match its SEC filing")
        expected_text = "$" + format(declared, ".2f") + " per share" if isinstance(declared, (int, float)) and not isinstance(declared, bool) else ""
        if (
            item.get("security_type") != "PREFERRED"
            or not expected_text
            or expected_text.lower() not in raw_context.lower()
            or "preferred stock" not in raw_context.lower()
        ):
            raise ValueError(f"{ticker}: preferred exclusion does not match its filing evidence")
        exclusions.append({
            "ticker": item.get("ticker"),
            "security_type": "PREFERRED",
            "declared_per_share": item.get("declared_per_share"),
            "status": "PREFERRED_STOCK_EXCLUDED_FROM_COMMON_DIVIDEND",
            "source_url": url,
            "source_type": item.get("source_type"),
            "accession_number": item.get("accession_number"),
            "evidence_sha256": sha,
        })

    return {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_commit_sha": SOURCE_SHA,
            "verification_run_url": VERIFICATION_URL,
            "scope": "TARGETED_SAMPLE",
            "full_scan_status": "NOT_RUN",
            "verified_event_count": len(events),
            "coverage_note": "仅 CAT/BAC 两家定向验证，并非完整覆盖",
        },
        "events": events,
        "exclusions": exclusions,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--events", default=str(SRC_EVENTS))
    parser.add_argument("--audit", default=str(SRC_AUDIT))
    parser.add_argument("--exclusions", default=str(SRC_EXCL))
    args = parser.parse_args()
    out = Path(args.out)

    missing = [
        path for path in (args.events, args.audit, args.exclusions)
        if not Path(path).exists()
    ]
    if missing:
        if out.exists():
            print(f"research sources unavailable ({len(missing)} missing); keeping existing snapshot")
            return 0
        print("no research sources and no existing snapshot")
        return 1

    try:
        built = build(
            _load(Path(args.events)),
            _load(Path(args.audit)),
            _load(Path(args.exclusions)),
        )
    except Exception as exc:
        print(f"refusing to overwrite dashboard data: {exc}")
        return 1

    if not built["events"]:
        if out.exists():
            print("no VERIFIED events; keeping existing snapshot")
            return 0
        print("no VERIFIED events and no existing snapshot")
        return 1

    if out.exists():
        try:
            old = json.loads(out.read_text(encoding="utf-8"))
            if old.get("events") == built["events"] and old.get("exclusions") == built["exclusions"]:
                built["metadata"]["generated_at"] = old.get("metadata", {}).get(
                    "generated_at", built["metadata"]["generated_at"]
                )
        except Exception:
            pass

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(built, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out} events={len(built['events'])} exclusions={len(built['exclusions'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
