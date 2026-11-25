#!/usr/bin/env python3
"""Atomic snapshot publish with validation and rollback-safe backup."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REQUIRED = {"ticker", "composite_tier", "tradability_status", "style_tags"}


def validate(data: dict):
    if not data.get("research_only") is True: raise ValueError("research_only missing")
    rows = data.get("rows")
    if not isinstance(rows, list) or len(rows) != 5600: raise ValueError(f"row count {len(rows) if rows else 0}")
    tickers = [r.get("ticker") for r in rows]
    if any(not isinstance(t, str) or not t for t in tickers): raise ValueError("bad ticker")
    if len(set(tickers)) != len(tickers): raise ValueError("duplicate ticker")
    for r in rows:
        if not REQUIRED.issubset(r): raise ValueError(f"missing fields {r.get('ticker')}")
        if r["composite_tier"] not in {"TIER_1", "TIER_2", "WATCH", "BLOCKED"}: raise ValueError("bad tier")
        if r["tradability_status"] not in {"ELIGIBLE_FOR_RESEARCH", "WATCH", "BLOCKED", "INSUFFICIENT_DATA"}: raise ValueError("bad status")
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--target", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--archive", type=Path, required=True)
    ap.add_argument("--corrupt", action="store_true")
    a = ap.parse_args()
    a.target.parent.mkdir(parents=True, exist_ok=True); a.archive.mkdir(parents=True, exist_ok=True)
    data = json.loads(a.source.read_text(encoding="utf-8"))
    if a.corrupt:
        data["rows"] = data["rows"][:10]
    n = validate(data)
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    # write temp in target dir; fsync; atomic replace
    fd, tmpname = tempfile.mkstemp(prefix=".fs2_", suffix=".tmp", dir=str(a.target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload); f.flush(); os.fsync(f.fileno())
        if a.target.exists():
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            shutil.copy2(a.target, a.archive / f"fs2_candidates_{ts}.json")
        os.replace(tmpname, a.target)
    except Exception:
        if os.path.exists(tmpname): os.unlink(tmpname)
        raise
    sha = hashlib.sha256(a.target.read_bytes()).hexdigest()
    manifest = {"published_at": datetime.now(timezone.utc).isoformat(), "rows": n, "sha256": sha,
                "version": data.get("version"), "prices_as_of": data.get("prices_as_of"),
                "fundamentals_as_of": data.get("fundamentals_as_of")}
    a.manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
