#!/usr/bin/env python3
"""Manual forward-capture entry point with a source whitelist.

No scheduler, service, or production hook. Run manually against one allowed URL.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from tools.research.event_capture_store import fetch, normalize_url, store_observation

ALLOWED_HOSTS = {"www.federalreserve.gov", "federalreserve.gov"}
ALLOWED_PREFIXES = ("/newsevents/pressreleases/", "/newsevents/press/")


def allowed(url: str) -> bool:
    p = urlsplit(normalize_url(url))
    return p.hostname in ALLOWED_HOSTS and any(p.path.startswith(x) for x in ALLOWED_PREFIXES)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", required=True)
    p.add_argument("--store", required=True)
    p.add_argument("--user-agent", default="wj-quant-research/1.0")
    p.add_argument("--backfill", action="store_true")
    args = p.parse_args(argv)
    if not allowed(args.url):
        raise SystemExit("URL not allowed by source whitelist")
    obs = fetch(args.url, datetime.now(timezone.utc), user_agent=args.user_agent)
    rec = store_observation(args.store, obs, backfill=args.backfill)
    print(json.dumps(rec, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
