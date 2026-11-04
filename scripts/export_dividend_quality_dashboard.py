#!/usr/bin/env python3
"""Export only verified P4.5 CAT/BAC dividends for the public dashboard.

Reads existing research JSON. No SEC access, no SEC_USER_AGENT, no strategy code.
"""
from __future__ import annotations
import argparse, json, re
from datetime import datetime, timezone
from pathlib import Path

SRC_EVENTS = Path("data/research/dividend_events_targeted_p45.json")
SRC_AUDIT = Path("data/research/dividend_event_field_audit_p45.json")
SRC_EXCL = Path("data/research/dividend_event_exclusions_p45.json")
OUT = Path("dashboard/data/dividend_quality.json")
SOURCE_SHA = "6c131858bb2eef4ff9fd219caf3171813c217e6e"
VERIFICATION_URL = "https://github.com/wijouyang-lab/us/actions/runs/41819727044"
SEC_HTTPS = re.compile(r"^https://www\.sec\.gov/", re.I)

REQUIRED = {"announcement":"VERIFIED","declared_per_share":"VERIFIED","security_type":"VERIFIED",
            "frequency":"VERIFIED","record_date":"VERIFIED","payment_date":"VERIFIED"}


def _safe_url(url: str) -> bool:
    return bool(url and SEC_HTTPS.match(url))


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build(events_doc, audit_doc, excl_doc):
    audit_hashes = {h["sha256"] for h in audit_doc.get("hashes", []) if h.get("sha256")}
    audit_by_ticker = {e["ticker"]: e for e in audit_doc.get("events", [])}
    events = []
    for e in events_doc.get("events", []):
        t = e.get("ticker")
        if e.get("verification_status") != "VERIFIED": continue
        a = audit_by_ticker.get(t)
        if not a or a.get("event_status") != "VERIFIED": continue
        fields = a.get("fields", {})
        if any(fields.get(k, {}).get("status") != v for k, v in REQUIRED.items()): continue
        if e.get("ex_date") is not None or e.get("ex_date_status") != "NOT_DISCLOSED_IN_FILING": continue
        sources = []
        for s in e.get("sources", []):
            if s.get("sha256") not in audit_hashes or not _safe_url(s.get("url","")): continue
            sources.append({"role":s.get("role"),"source_type":s.get("source_type"),
                            "url":s.get("url"),"filename":s.get("filename"),"sha256":s.get("sha256")})
        if len({x["role"] for x in sources}) < 2: continue
        events.append({
            "ticker":t,"event_type":e.get("event_type"),"security_type":e.get("security_type"),
            "declared_per_share":e.get("declared_per_share"),
            "previous_per_share":e.get("previous_per_share"),
            "previous_per_share_status":e.get("previous_per_share_status"),
            "increase_per_share":e.get("increase_per_share"),"increase_pct":e.get("increase_pct"),
            "announcement_date":e.get("announcement_date"),"record_date":e.get("record_date"),
            "payment_date":e.get("payment_date"),"ex_date":None,
            "ex_date_status":e.get("ex_date_status"),
            "verification_status":e.get("verification_status"),
            "sources":sources,"source_url":e.get("source_url"),"source_type":e.get("source_type"),
            "document_role":"EXHIBIT","accession_number":e.get("accession_number"),
            "evidence_sha256":e.get("evidence_sha256"),
        })
    exclusions = []
    for x in excl_doc.get("exclusions", []):
        exclusions.append({"ticker":x.get("ticker"),"security_type":"PREFERRED",
            "declared_per_share":x.get("declared_per_share"),
            "status":"PREFERRED_STOCK_EXCLUDED_FROM_COMMON_DIVIDEND",
            "source_url":x.get("source_url"),"source_type":x.get("source_type"),
            "accession_number":x.get("accession_number"),"evidence_sha256":x.get("evidence_sha256")})
    return {
        "metadata":{"generated_at":datetime.now(timezone.utc).isoformat(),
            "source_commit_sha":SOURCE_SHA,"verification_run_url":VERIFICATION_URL,
            "scope":"TARGETED_SAMPLE","full_scan_status":"NOT_RUN",
            "verified_event_count":len(events),
            "coverage_note":"仅 CAT/BAC 两家定向验证，并非完整覆盖"},
        "events":events,"exclusions":exclusions,
    }


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--out",default=str(OUT)); ap.add_argument("--events",default=str(SRC_EVENTS))
    ap.add_argument("--audit",default=str(SRC_AUDIT)); ap.add_argument("--exclusions",default=str(SRC_EXCL))
    a=ap.parse_args(); out=Path(a.out)
    missing=[p for p in (a.events,a.audit,a.exclusions) if not Path(p).exists()]
    if missing:
        if out.exists():
            print(f"research sources unavailable ({len(missing)} missing); keeping existing snapshot")
            return 0
        print("no research sources and no existing snapshot"); return 1
    try:
        built=build(_load(Path(a.events)),_load(Path(a.audit)),_load(Path(a.exclusions)))
    except Exception as e:
        print(f"refusing to overwrite dashboard data: {e}"); return 1
    if not built["events"]:
        if out.exists():
            print("no VERIFIED events; keeping existing snapshot"); return 0
        print("no VERIFIED events and no existing snapshot"); return 1
    if out.exists():
        try:
            old=json.loads(out.read_text(encoding="utf-8"))
            if old.get("events")==built["events"] and old.get("exclusions")==built["exclusions"]:
                built["metadata"]["generated_at"]=old.get("metadata",{}).get("generated_at",built["metadata"]["generated_at"])
        except Exception:
            pass
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(built,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(f"wrote {out} events={len(built['events'])} exclusions={len(built['exclusions'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
