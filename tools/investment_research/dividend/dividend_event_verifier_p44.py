"""Field-level verification for P4.4 dividend events."""
from __future__ import annotations
from tools.investment_research.dividend.evidence_registry import event_id

CORE = ("ticker","event_type","security_type","declared_per_share","announcement_date",
        "source_url","accession_number","evidence_sha256")


def verify(events: list[dict], fetched_accessions: set[str] | None = None) -> list[dict]:
    out = []
    for e in events:
        x = dict(e)
        missing = [k for k in CORE if not x.get(k)]
        if x.get("security_type") != "COMMON":
            continue
        if fetched_accessions is not None and x.get("accession_number") not in fetched_accessions:
            x["verification_status"] = "SOURCE_FETCH_FAILED"; out.append(x); continue
        if missing:
            x["verification_status"] = "PARTIALLY_VERIFIED"; x["missing_fields"] = missing
        else:
            x["verification_status"] = "VERIFIED"
        x["ex_date_status"] = x.get("ex_date_status") or ("EX_DATE_UNAVAILABLE" if not x.get("ex_date") else "OK")
        x["event_id"] = x.get("event_id") or event_id(
            ticker=x["ticker"], event_type=x["event_type"], event_date=x["announcement_date"],
            source_url=x["source_url"], evidence_sha256=x["evidence_sha256"])
        out.append(x)
    return out


def dedupe(events: list[dict]) -> list[dict]:
    out = {}
    for e in events:
        key = (e["ticker"], e["event_type"], e.get("announcement_date"),
               e.get("declared_per_share"), e.get("security_type"))
        if key not in out: out[key] = e
        else: out[key].setdefault("alternate_sources", []).append(e.get("source_url"))
    return list(out.values())
