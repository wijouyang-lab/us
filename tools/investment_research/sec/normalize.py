"""Normalize SEC CompanyFacts into traceable duration/instant facts."""
from __future__ import annotations
from dataclasses import dataclass, asdict, field
from datetime import date, datetime, timezone
from typing import Iterable


@dataclass
class Fact:
    cik: str; taxonomy: str; concept: str; unit: str; value: float
    start: str | None; end: str; filed: str; form: str; accession: str
    fy: int | None = None; fp: str | None = None; frame: str | None = None
    accepted_at: str | None = None; first_seen_at: str | None = None
    source: str = "SEC CompanyFacts"; fetched_at: str = ""
    sha256: str = ""; availability_quality: str = "FILED_DATE_ONLY"
    def to_dict(self): return asdict(self)


def duration_days(start: str | None, end: str) -> int | None:
    if not start: return None
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def extract(companyfacts: dict, *, cik: str, fetched_at: str, sha256: str = "",
            accepted: dict[str, str] | None = None) -> list[Fact]:
    out = []
    for taxonomy, concepts in (companyfacts.get("facts") or {}).items():
        for concept, obj in concepts.items():
            for unit, rows in (obj.get("units") or {}).items():
                for r in rows:
                    if "val" not in r or "end" not in r: continue
                    acc = r.get("accn", "")
                    q = "ACCEPTANCE_ESTIMATE" if accepted and acc in accepted else "FILED_DATE_ONLY"
                    out.append(Fact(cik=cik, taxonomy=taxonomy, concept=concept, unit=unit,
                        value=float(r["val"]), start=r.get("start"), end=r["end"],
                        filed=r.get("filed", ""), form=r.get("form", ""), accession=acc,
                        fy=r.get("fy"), fp=r.get("fp"), frame=r.get("frame"),
                        accepted_at=(accepted or {}).get(acc), fetched_at=fetched_at,
                        sha256=sha256, availability_quality=q,
                        first_seen_at=None))
    return out


def available(f: Fact, as_of: str | None) -> bool:
    if not as_of: return True
    cutoff = datetime.fromisoformat(as_of.replace("Z", "+00:00")).date() if "T" in as_of else date.fromisoformat(as_of)
    try: return date.fromisoformat(f.filed) <= cutoff
    except ValueError: return False
