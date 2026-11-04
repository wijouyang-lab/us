"""Evidence registry with deterministic IDs and validation."""
from __future__ import annotations
import hashlib, json
from datetime import date


def event_id(*, ticker, event_type, event_date, source_url, evidence_sha256):
    raw = f"{ticker.upper()}|{event_type}|{event_date}|{source_url}|{evidence_sha256}"
    return "DIV-" + hashlib.sha256(raw.encode()).hexdigest()[:20]


def split_id(*, ticker, effective_date, ratio, source_url, evidence_sha256):
    raw = f"{ticker.upper()}|SPLIT|{effective_date}|{ratio}|{source_url}|{evidence_sha256}"
    return "SPL-" + hashlib.sha256(raw.encode()).hexdigest()[:20]


def validate_source(url: str):
    if not url or not url.startswith("https://"):
        raise ValueError("official https source URL required")


def validate_date(value: str | None, field: str):
    if value is not None:
        date.fromisoformat(value)


def load(path):
    p = __import__("pathlib").Path(path)
    return json.loads(p.read_text()) if p.exists() else []


def save(path, rows):
    p = __import__("pathlib").Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
