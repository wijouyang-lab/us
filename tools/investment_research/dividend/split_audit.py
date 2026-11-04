"""Split-basis evidence for per-share dividend history. No price inference."""
from __future__ import annotations
import hashlib
from dataclasses import dataclass, asdict
from datetime import date

@dataclass(frozen=True)
class SplitEvidence:
    ticker: str; ratio: float; announcement_date: str; effective_date: str
    source_url: str; evidence_sha256: str; verification_status: str = "UNVERIFIED"

def make_evidence(*, ticker, ratio, announcement_date, effective_date, source_url, evidence) -> SplitEvidence:
    if ratio <= 0: raise ValueError("ratio must be positive")
    date.fromisoformat(announcement_date); date.fromisoformat(effective_date)
    if not source_url.startswith("http"): raise ValueError("source URL required")
    raw = evidence.encode() if isinstance(evidence,str) else evidence
    return SplitEvidence(ticker, ratio, announcement_date, effective_date, source_url,
                         hashlib.sha256(raw).hexdigest())

def split_status(ticker: str, evidence: list[SplitEvidence]) -> dict:
    rows = [e for e in evidence if e.ticker.upper() == ticker.upper() and e.verification_status == "VERIFIED"]
    if not rows:
        return {"ticker": ticker.upper(), "status": "DPS_SPLIT_BASIS_UNVERIFIED",
                "cagr_allowed": False, "evidence_count": 0}
    return {"ticker": ticker.upper(), "status": "VERIFIED", "cagr_allowed": True,
            "events": [asdict(e) for e in rows]}
