#!/usr/bin/env python3
"""Audit capture JSONL records against the PIT admission rules."""
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
    p.add_argument("--decision-at", default=None)
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    files = []
    for pat in args.store:
        files.extend(glob.glob(pat))
    records = []
    for f in files:
        for line in Path(f).read_text(encoding="utf-8").splitlines():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    latest = {}
    for r in records:
        if r.get("event_id"):
            latest[r["event_id"]] = r
    decisions = [admit(r, decision_at=args.decision_at) for r in latest.values()]
    reasons = Counter(x for d in decisions for x in d["reasons"])
    by_event = {d["event_id"]: d["reasons"] for d in decisions}
    payload = {
        "records_total": len(records),
        "unique_events": len(latest),
        "real_first_seen_records": sum(
            1 for r in latest.values()
            if r.get("first_seen_at_utc") and not r.get("is_simulated") and not r.get("is_historical_backfill")
        ),
        "simulated_records": sum(1 for r in latest.values() if r.get("is_simulated")),
        "late_observations": sum(
            1 for r in latest.values()
            if r.get("observation_kind") == "late_observation_of_old_event" or r.get("pit_status") == "late_observation_not_pit"
        ),
        "historical_backfills": sum(1 for r in latest.values() if r.get("is_historical_backfill")),
        "published_evidence_insufficient": sum(
            1 for r in latest.values() if not r.get("published_at") or r.get("parse_status") != "exact"
        ),
        "decision_evidence_insufficient": sum(1 for d in decisions if "decision_time_missing" in d["reasons"]),
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
