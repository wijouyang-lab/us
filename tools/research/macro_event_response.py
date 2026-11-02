#!/usr/bin/env python3
"""Official macro event feasibility audit.

Stops before empirical testing if official event coverage is insufficient.
No paid data, no broker, no orders.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd
import requests

START = "2007-01-01"
END = "2026-10-30"
SOURCES = {
    "cpi": "https://permanent.fdlp.gov/gpo146835/gpo146835/www.bls.gov/bls/news-release/cpi.htm",
    "empsit": "https://permanent.fdlp.gov/gpo146835/gpo146835/www.bls.gov/bls/news-release/empsit.htm",
    "cpi_live": "https://www.bls.gov/bls/news-release/cpi.htm",
    "empsit_live": "https://www.bls.gov/bls/news-release/empsit.htm",
}
FOMC = "https://www.federalreserve.gov/monetarypolicy/fomchistorical{y}.htm"
FOMC_RECENT = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"


def fetch(url: str):
    try:
        r = requests.get(url, timeout=45, headers={"User-Agent": "Mozilla/5.0 research-audit"})
        return r.status_code, r.text, hashlib.sha256(r.content).hexdigest()
    except Exception as exc:  # noqa: BLE001
        return None, "", str(exc)


def parse_bls(html: str, family: str):
    pat = rf'(?:cpi|empsit)_(\d{{8}})\.(?:htm|txt)'
    out = {}
    for m in re.finditer(pat, html):
        ymd = m.group(1)
        d = datetime.strptime(ymd, "%m%d%Y").date()
        if not (date(2007, 1, 1) <= d <= date(2026, 10, 30)):
            continue
        key = f"{family}_{d.isoformat()}"
        out[key] = {
            "event_id": key, "event_type": family, "publication_date": d.isoformat(),
            "publication_time": "08:30:00", "timezone": "America/New_York",
            "time_type": "scheduled_standard", "timestamp_confidence": "medium",
            "verification_status": "official_archive_date_scheduled_time",
        }
    return list(out.values())


def parse_fomc(html: str):
    out = {}
    for m in re.finditer(r'monetary/?(\d{8})a\.htm', html):
        d = pd.Timestamp(m.group(1)).date()
        if not (date(2007, 1, 1) <= d <= date(2026, 10, 30)):
            continue
        key = f"fomc_{d.isoformat()}"
        out[key] = {
            "event_id": key, "event_type": "fomc", "publication_date": d.isoformat(),
            "publication_time": "14:00:00", "timezone": "America/New_York",
            "time_type": "scheduled_policy_release", "timestamp_confidence": "medium",
            "verification_status": "official_statement_date_scheduled_time",
        }
    return list(out.values())


def align(event, sessions):
    d = pd.Timestamp(event["publication_date"])
    t = pd.Timestamp(f"{event['publication_date']} {event['publication_time']}").tz_localize("America/New_York")
    # BLS 08:30 is before the 09:30 open; FOMC 14:00 is after it.
    preopen = t.time() < pd.Timestamp("09:30").time()
    if d in sessions and preopen:
        s = d
    else:
        later = sessions[sessions > d]
        s = later[0] if len(later) else pd.NaT
    return s


def audit(events, sessions):
    by_year = {}
    for e in events:
        y = e["publication_date"][:4]
        by_year.setdefault(e["event_type"], {}).setdefault(y, 0)
        by_year[e["event_type"]][y] += 1
    coverage = {}
    for fam in ("cpi", "empsit", "fomc"):
        coverage[fam] = {str(y): by_year.get(fam, {}).get(str(y), 0) for y in range(2007, 2027)}
    missing = {}
    for fam in ("cpi", "empsit"):
        missing[fam] = [y for y in range(2021, 2027) if coverage[fam][str(y)] == 0]
    missing["fomc"] = [y for y in range(2007, 2027) if coverage["fomc"][str(y)] == 0]
    duplicate_ids = len(events) - len({e["event_id"] for e in events})
    return {"coverage_by_year": coverage, "missing_years": missing,
            "duplicate_event_ids": duplicate_ids,
            "data_sufficient": not any(missing.values()),
            "status": "DATA_BLOCKED" if any(missing.values()) else "READY"}


def build(data_dir: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    sources = {}
    events = []
    raw = {}
    for key in ("cpi", "empsit"):
        status, text, sha = fetch(SOURCES[key])
        sources[key] = {"url": SOURCES[key], "status": status, "sha256": sha}
        raw[key] = text
        if status == 200:
            events += parse_bls(text, key)
    for y in range(2007, 2027):
        url = FOMC.format(y=y)
        status, text, sha = fetch(url)
        sources[f"fomc_{y}"] = {"url": url, "status": status, "sha256": sha}
        if status == 200:
            events += parse_fomc(text)
    status, text, sha = fetch(FOMC_RECENT)
    sources["fomc_recent"] = {"url": FOMC_RECENT, "status": status, "sha256": sha}
    if status == 200:
        events += parse_fomc(text)
    # live BLS access check is part of the audit, not a fallback
    for key in ("cpi_live", "empsit_live"):
        status, text, sha = fetch(SOURCES[key])
        sources[key] = {"url": SOURCES[key], "status": status,
                        "sha256": sha if status == 200 else None}
    dedup = {e["event_id"]: e for e in events}
    events = list(dedup.values())
    retrieved = datetime.now(timezone.utc).isoformat()
    for e in events:
        if e["event_type"] in ("cpi", "empsit"):
            e["official_source"] = "BLS"
            e["official_source_url"] = (f"https://www.bls.gov/news.release/archives/"
                                        f"{e['event_type']}_{pd.Timestamp(e['publication_date']).strftime('%m%d%Y')}.htm")
            e["reference_period"] = "BLS release period not parsed from archive index"
            e["source_content_sha256"] = sources[e["event_type"]]["sha256"]
            e["hash_scope"] = "official_archive_index"
        else:
            e["official_source"] = "Federal Reserve Board"
            e["official_source_url"] = ("https://www.federalreserve.gov/newsevents/pressreleases/"
                                        f"monetary{pd.Timestamp(e['publication_date']).strftime('%Y%m%d')}a.htm")
            e["reference_period"] = "FOMC statement"
            e["source_content_sha256"] = sources.get("fomc_recent", {}).get("sha256")
            e["hash_scope"] = "official_calendar_or_historical_page"
        e["source_retrieved_at_utc"] = retrieved
        local = pd.Timestamp(f"{e['publication_date']} {e['publication_time']}").tz_localize("America/New_York")
        e["publication_time_utc"] = local.tz_convert("UTC").isoformat()
    events.sort(key=lambda x: (x["publication_date"], x["event_type"]))
    spy = pd.read_csv(data_dir / "SPY.csv")
    spy["Date"] = pd.to_datetime(spy["Date"], utc=True).dt.tz_convert(None).dt.normalize()
    sessions = pd.DatetimeIndex(sorted(set(spy.Date)))
    sessions = pd.DatetimeIndex([s for s in sessions if s >= pd.Timestamp(START)])
    cal = xcals.get_calendar("XNYS")
    sessions = pd.DatetimeIndex([s for s in sessions if cal.is_session(s)])
    for e in events:
        s = align(e, sessions)
        e["tradable_session"] = s.date().isoformat() if pd.notna(s) else None
        e["alignment_status"] = "ALIGNED" if pd.notna(s) else "NO_SESSION"
    a = audit(events, sessions)
    report = {"start": START, "end": END, "market_data_asof": str(sessions[-1].date()),
              "sources": sources, "audit": a, "events": len(events),
              "event_counts": {k: sum(1 for e in events if e["event_type"] == k)
                               for k in ("cpi", "empsit", "fomc")},
              "study_status": "NOT_RUN_DATA_BLOCKED" if not a["data_sufficient"] else "READY",
              "note": "No empirical event study is run while status is DATA_BLOCKED."}
    pd.DataFrame(events).to_csv(out_dir / "events.csv", index=False)
    pd.DataFrame(events)[["event_id", "event_type", "publication_date", "publication_time",
                          "timezone", "tradable_session", "alignment_status"]].to_csv(
        out_dir / "session_alignment.csv", index=False)
    (out_dir / "audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    files = {}
    for p in ("events.csv", "session_alignment.csv", "audit.json"):
        q = out_dir / p
        files[p] = {"sha256": hashlib.sha256(q.read_bytes()).hexdigest(), "bytes": q.stat().st_size}
    (out_dir / "manifest.json").write_text(json.dumps(
        {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "files": files,
         "study_status": report["study_status"]}, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", type=Path, default=Path("data/research/volume_shock_reversal"))
    p.add_argument("--output", type=Path, default=Path("data/research/macro_event_response"))
    a = p.parse_args()
    print(json.dumps(build(a.data_dir, a.output), indent=2))
