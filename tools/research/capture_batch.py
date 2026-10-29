#!/usr/bin/env python3
"""Manual batch capture with batch ID and resumable duplicate handling.

No scheduler, daemon, or external trigger. URLs are whitelisted Fed pages.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from tools.research.event_capture_store import fetch, store_observation
from tools.research.forward_capture import allowed


def _load(path: Path):
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def run(urls: list[str], store: Path, *, user_agent: str, backfill: bool = False,
        batch_id: str | None = None) -> dict:
    batch_id = batch_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    started = datetime.now(timezone.utc)
    before = _load(store)
    old = {}
    for r in before:
        if r.get("event_id"):
            old[r["event_id"]] = r
    counts = {"new": 0, "duplicate": 0, "updated": 0, "failed": 0}
    records = []
    for url in urls:
        if not allowed(url):
            records.append({"url": url, "status": "rejected_url"})
            counts["failed"] += 1
            continue
        obs = fetch(url, user_agent=user_agent)
        rec = store_observation(store, obs, backfill=backfill)
        records.append({"url": url, "event_id": rec.get("event_id"),
                        "http_status": rec.get("http_status"),
                        "parse_status": rec.get("parse_status")})
        if rec.get("parse_status") not in ("exact", "date_only"):
            counts["failed"] += 1
        elif rec.get("event_id") not in old:
            counts["new"] += 1
        elif int(rec.get("version") or 0) > int(old[rec.get("event_id")].get("version") or 0):
            counts["updated"] += 1
        else:
            counts["duplicate"] += 1
    summary = {"batch_id": batch_id, "started_at_utc": started.isoformat().replace("+00:00", "Z"),
               "finished_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
               "counts": counts, "records": records}
    Path(str(store) + ".batches.jsonl").open("a", encoding="utf-8").write(
        json.dumps(summary, ensure_ascii=False) + "\n")
    return summary


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", action="append", required=True)
    p.add_argument("--store", required=True)
    p.add_argument("--user-agent", default="wj-quant-research/1.0")
    p.add_argument("--backfill", action="store_true")
    p.add_argument("--batch-id", default=None)
    args = p.parse_args(argv)
    print(json.dumps(run(args.url, Path(args.store), user_agent=args.user_agent,
                         backfill=args.backfill, batch_id=args.batch_id), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
