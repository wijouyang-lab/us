#!/usr/bin/env python3
"""Minimal event observation store with immutable first-seen semantics.

No production hooks. Live observations preserve first_seen on re-fetch.
Historical backfills never receive a historical first_seen.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

STORE_VERSION = 1


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def content_hash(text: str) -> str:
    start = text.find("For release at")
    end = text.find("Implementation Note", start)
    segment = text[start:end] if start >= 0 and end > start else text
    visible = re.sub(r"<script.*?</script>|<style.*?</style>", " ", segment, flags=re.S | re.I)
    visible = re.sub(r"<[^>]+>", " ", visible)
    normalized = re.sub(r"\s+", " ", visible).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def parse_fomc_statement(html: str, url: str, fetched_at: datetime) -> dict[str, Any]:
    title_m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    title = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else ""
    m = re.search(r"monetary/?(\d{8})a\.htm", url)
    if not m:
        return {"event_id": None, "parse_status": "failed", "parse_reason": "no_event_id",
                "title": title}
    event_id = m.group(1)
    hr = re.search(r"For release at\s+(\d{1,2}):(\d{2})\s*(a\.m\.|p\.m\.)\s*(EDT|EST)", html, re.I)
    rec = {"event_id": event_id, "source_url": url, "event_type": "FOMC_statement",
           "title": title, "fetched_at_utc": _iso(fetched_at),
           "content_hash": content_hash(html), "http_status": 200}
    if not hr:
        rec.update({"published_at": None, "release_time_local": None,
                    "source_timezone": None, "parse_status": "date_only"})
        return rec
    hh, mm, ampm, tz = int(hr.group(1)), int(hr.group(2)), hr.group(3).lower(), hr.group(4).upper()
    if ampm.startswith("p") and hh != 12:
        hh += 12
    if ampm.startswith("a") and hh == 12:
        hh = 0
    from zoneinfo import ZoneInfo
    dt = datetime(int(event_id[:4]), int(event_id[4:6]), int(event_id[6:8]), hh, mm,
                  tzinfo=ZoneInfo("America/New_York"))
    rec.update({"published_at": _iso(dt), "release_time_local": f"{hr.group(1)}:{hr.group(2)} {ampm.upper()} {tz}",
                "source_timezone": tz, "parse_status": "exact"})
    return rec


def store_observation(path: str | Path, obs: dict[str, Any], *, backfill: bool = False) -> dict[str, Any]:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    old = None
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                x = json.loads(line)
            except json.JSONDecodeError:
                continue
            if x.get("event_id") == obs.get("event_id"):
                old = x
                break
    rec = dict(obs)
    rec["is_historical_backfill"] = bool(backfill)
    if backfill:
        rec["first_seen_at_utc"] = None
        rec["pit_status"] = "retrospective_non_PIT"
        rec["version"] = int(old.get("version", 0)) + 1 if old else 1
    else:
        rec["first_seen_at_utc"] = old.get("first_seen_at_utc") if old else obs.get("fetched_at_utc")
        rec["pit_status"] = "forward_observed" if rec.get("parse_status") == "exact" else "capture_error"
        same = old and old.get("content_hash") == obs.get("content_hash")
        rec["version"] = old.get("version", 0) if same else (old.get("version", 0) + 1 if old else 1)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def fetch(url: str, now: datetime | None = None, *, timeout: int = 20) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    try:
        r = requests.get(url, headers={"User-Agent": "wj-quant-research/1.0"}, timeout=timeout)
        if r.status_code != 200:
            return {"event_id": None, "source_url": url, "http_status": r.status_code,
                    "parse_status": "http_error", "fetched_at_utc": _iso(now)}
        return parse_fomc_statement(r.text, url, now)
    except Exception as exc:
        return {"event_id": None, "source_url": url, "http_status": None,
                "parse_status": "network_error", "error": f"{type(exc).__name__}: {exc}",
                "fetched_at_utc": _iso(now)}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", required=True)
    p.add_argument("--store", required=True)
    p.add_argument("--backfill", action="store_true")
    args = p.parse_args(argv)
    obs = fetch(args.url)
    out = store_observation(args.store, obs, backfill=args.backfill)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
