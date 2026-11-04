"""Evidence-gated dividend events. Annual numeric change is not an event."""
from __future__ import annotations
import hashlib
from dataclasses import dataclass, asdict
from datetime import date

EVENT_TYPES = {"DECLARED","EX_DATE","RECORD_DATE","PAYMENT_DATE","REDUCED","SUSPENDED","RESUMED","INCREASED"}


@dataclass(frozen=True)
class DividendEvent:
    event_id: str; ticker: str; cik: str; event_type: str; event_date: str
    source_url: str; source_type: str; evidence_sha256: str
    cash_per_share: float | None = None
    status: str = "UNVERIFIED"

    def __post_init__(self):
        if self.event_type not in EVENT_TYPES: raise ValueError("unknown dividend event type")
        date.fromisoformat(self.event_date)
        if not self.source_url.startswith("http"): raise ValueError("source_url required")
        if not self.evidence_sha256: raise ValueError("evidence hash required")


def make_event(*, ticker, cik, event_type, event_date, source_url, source_type,
               evidence: bytes | str, cash_per_share=None) -> DividendEvent:
    raw = evidence.encode() if isinstance(evidence, str) else evidence
    h = hashlib.sha256(raw).hexdigest()
    eid = "DIV-" + hashlib.sha256(f"{ticker}|{event_type}|{event_date}|{source_url}|{h}".encode()).hexdigest()[:16]
    return DividendEvent(eid, ticker, cik, event_type, event_date, source_url, source_type, h, cash_per_share)


def dedupe(events: list[DividendEvent]) -> list[DividendEvent]:
    return list({e.event_id: e for e in events}.values())


def annual_change_flags(series: list[dict]) -> list[dict]:
    """Descriptive flags only; explicitly not DECLARED/INCREASED events."""
    out = []
    for a, b in zip(series, series[1:]):
        if a["value"] <= 0: continue
        g = (b["value"] - a["value"]) / a["value"]
        if g <= -0.05: out.append({"type": "POSSIBLE_REDUCTION", "year": b["end"], "change": g, "is_event": False})
    return out
