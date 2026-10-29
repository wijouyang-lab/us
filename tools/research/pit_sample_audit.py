#!/usr/bin/env python3
"""Audit capture JSONL records against explicit PIT admission rules."""
from __future__ import annotations

import argparse
import glob
import json
from collections import Counter
from pathlib import Path

from tools.research.pit_admission import admit


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--store", action="append", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    files = []
    for pat in args.store:
        matched = [x for x in glob.glob(pat) if not x.endswith(".batches.jsonl")]
        if not matched:
            raise SystemExit(f"store pattern matched no files: {pat}")
        files.extend(matched)
    files = sorted(set(files))
    records = []
    invalid_lines = 0
    empty_files = []
    for f in files:
        text = Path(f).read_text(encoding="utf-8")
        if not text.strip():
            empty_files.append(f)
            continue
        for line in text.splitlines():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                invalid_lines += 1
    latest = {}
    for r in records:
        if not r.get("event_id"):
            continue
        old = latest.get(r["event_id"])
        key = (int(r.get("version") or 0), str(r.get("fetched_at_utc") or ""))
        if old is None or key >= (int(old.get("version") or 0), str(old.get("fetched_at_utc") or "")):
            latest[r["event_id"]] = r
    decisions = [admit(r) for r in latest.values()]
    reasons = Counter(x for d in decisions for x in d["reasons"])
    by_event = {d["event_id"]: d["reasons"] for d in decisions}
    payload = {
        "status": "ok" if records else "no_valid_records",
        "files": files,
        "empty_files": empty_files,
        "invalid_lines": invalid_lines,
        "records_total": len(records),
        "unique_events": len(latest),
        "real_first_seen_records": sum(
            1 for r in latest.values()
            if r.get("first_seen_at_utc") and r.get("is_simulated") is False
            and not r.get("is_historical_backfill")
        ),
        "simulated_records": sum(1 for r in latest.values() if r.get("is_simulated") is True),
        "simulation_flag_missing": sum(1 for r in latest.values() if r.get("is_simulated") is None),
        "late_observations": sum(
            1 for r in latest.values()
            if r.get("observation_kind") == "late_observation_of_old_event" or r.get("pit_status") == "late_observation_not_pit"
        ),
        "historical_backfills": sum(1 for r in latest.values() if r.get("is_historical_backfill")),
        "published_evidence_insufficient": sum(
            1 for r in latest.values()
            if not r.get("published_at") or r.get("published_at_evidence") not in {"official_release_time_in_page", "verified_sgml_header"}
        ),
        "decision_evidence_insufficient": sum(1 for d in decisions if "decision_time_missing" in d["reasons"] or "decision_evidence_missing" in d["reasons"]),
        "pit_admitted": sum(1 for d in decisions if d["admitted"]),
        "rejection_reason_counts": dict(reasons),
        "events": by_event,
        "stores": files,
    }
    Path(args.output).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
