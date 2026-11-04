"""Resumable P4.5 SEC manifest with expected inventory and retry state."""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone


def load(path="data/research/sec_fetch_manifest_p45.json"):
    p = Path(path)
    m = json.loads(p.read_text()) if p.exists() else {}
    m.setdefault("generated_at", None); m.setdefault("expected_accessions", []); m.setdefault("accessions", {})
    return m


def save(m, path="data/research/sec_fetch_manifest_p45.json"):
    m["generated_at"] = datetime.now(timezone.utc).isoformat()
    Path(path).write_text(json.dumps(m, indent=2), encoding="utf-8")


def set_expected(m, entries):
    """entries: [{accession,ticker}] from submissions; keeps prior retry state."""
    m["expected_accessions"] = sorted({e["accession"] for e in entries})
    for e in entries:
        m["accessions"].setdefault(e["accession"], {
            "ticker": e["ticker"], "status": "NOT_ATTEMPTED", "index_status": None,
            "primary_status": None, "exhibit_statuses": [], "documents": [],
            "text_scanned": False, "retry_count": 0, "last_attempt": None,
            "error_status": None})


def upsert(m, ticker, accession, fetch):
    old = m["accessions"].get(accession, {})
    docs = fetch.get("documents", [])
    primary = fetch.get("primary") or {}
    exhibits = fetch.get("exhibits", [])
    m["accessions"][accession] = {
        "ticker": ticker, "status": fetch.get("status_text"),
        "index_status": "OK" if fetch.get("index_url") else "FAILED",
        "primary_status": primary.get("status"), "exhibit_statuses": [x.get("status") for x in exhibits],
        "documents": docs, "primary": primary, "exhibits": exhibits,
        "downloaded": fetch.get("downloaded", 0), "failed": fetch.get("failed", 0),
        "text_scanned": old.get("text_scanned", False),
        "retry_count": old.get("retry_count", 0) + (0 if fetch.get("status_text") == "FETCHED_COMPLETE" else 1),
        "last_attempt": datetime.now(timezone.utc).isoformat(),
        "error_status": None if fetch.get("status_text") == "FETCHED_COMPLETE" else fetch.get("status_text"),
    }


def mark_text_scanned(m, accession):
    if accession in m["accessions"]:
        m["accessions"][accession]["text_scanned"] = True


def accession_complete(a: dict) -> bool:
    if a.get("status") != "FETCHED_COMPLETE" or not a.get("text_scanned"): return False
    docs = a.get("documents", [])
    if not docs: return False
    if any(d.get("status") != 200 or not d.get("sha256") for d in docs): return False
    return True


def should_attempt(m, accession) -> bool:
    return not accession_complete(m["accessions"].get(accession, {}))


def complete(m) -> bool:
    expected = set(m.get("expected_accessions", []))
    if not expected: return False
    return all(accession_complete(m["accessions"].get(a, {})) for a in expected)
