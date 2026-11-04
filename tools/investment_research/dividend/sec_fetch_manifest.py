"""Resumable SEC fetch manifest: one record per accession/document."""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone


def load(path="data/research/sec_fetch_manifest_p45.json"):
    p = Path(path); return json.loads(p.read_text()) if p.exists() else {"generated_at": None, "accessions": {}}


def save(m, path="data/research/sec_fetch_manifest_p45.json"):
    m["generated_at"] = datetime.now(timezone.utc).isoformat()
    Path(path).write_text(json.dumps(m, indent=2), encoding="utf-8")


def upsert(m: dict, ticker: str, accession: str, fetch: dict):
    m["accessions"][accession] = {"ticker": ticker, "status": fetch.get("status_text"),
        "index_url": fetch.get("index_url"), "documents": fetch.get("documents", []),
        "primary": fetch.get("primary"), "exhibits": fetch.get("exhibits", []),
        "downloaded": fetch.get("downloaded", 0), "failed": fetch.get("failed", 0)}


def complete(m: dict) -> bool:
    return bool(m.get("accessions")) and all(
        x.get("status") in ("FETCHED_COMPLETE", "FETCHED_PARTIAL") for x in m["accessions"].values())
