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
from urllib.parse import urljoin, urlparse

import exchange_calendars as xcals
import pandas as pd
import requests

START = "2007-01-01"
END = "2026-10-30"
SOURCES = {
    "cpi": "https://www.bls.gov/bls/news-release/cpi.htm",
    "empsit": "https://www.bls.gov/bls/news-release/empsit.htm",
}
LEGACY_SOURCES = {
    "cpi": "https://permanent.fdlp.gov/gpo146835/gpo146835/www.bls.gov/bls/news-release/cpi.htm",
    "empsit": "https://permanent.fdlp.gov/gpo146835/gpo146835/www.bls.gov/bls/news-release/empsit.htm",
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
    pat = rf'href="([^"]*(?:cpi|empsit)_(\d{{8}})\.(?:htm|txt))"'
    out = {}
    for m in re.finditer(pat, html):
        href, ymd = m.group(1), m.group(2)
        d = datetime.strptime(ymd, "%m%d%Y").date()
        if not (date(2007, 1, 1) <= d <= date(2026, 10, 30)):
            continue
        key = f"{family}_{d.isoformat()}"
        out[key] = {
            "event_id": key, "event_type": family, "publication_date": d.isoformat(),
            "publication_time": None, "timezone": "America/New_York",
            "time_type": "date_only", "timestamp_confidence": "none",
            "verification_status": "official_archive_link",
            "_source_href": href,
        }
    return list(out.values())


def parse_bls_legacy(html: str, family: str):
    """Legacy FDLP archive fallback: filenames only, never treated as live/official timestamp."""
    out = {}
    for m in re.finditer(rf"(?:cpi|empsit)_(\d{{8}})\.(?:htm|txt)", html):
        d = datetime.strptime(m.group(1), "%m%d%Y").date()
        if not (date(2007, 1, 1) <= d <= date(2026, 10, 30)):
            continue
        key = f"{family}_{d.isoformat()}"
        out[key] = {"event_id": key, "event_type": family, "publication_date": d.isoformat(),
                    "publication_time": None, "timezone": "America/New_York",
                    "time_type": "date_only", "timestamp_confidence": "none",
                    "verification_status": "legacy_fdlp_index_only"}
    return list(out.values())


def parse_embargo(html: str):
    """Parse an explicitly documented BLS embargo-until line."""
    text = re.sub(r"\s+", " ", html)
    m = re.search(
        r"embargoed until\s+(\d{1,2}:\d{2}\s*[ap]\.?m\.?)\s*(?:\(?(?:ET|EST|EDT)\)?)?"
        r"\s*(?:on\s+)?(?:[A-Z][a-z]+,\s*)?([A-Z][a-z]+ \d{1,2}, \d{4})", text, re.I)
    if not m:
        return None
    timestr = m.group(1).lower().replace(".", "").replace(" ", "")
    t = datetime.strptime(timestr, "%I:%M%p").time()
    d = datetime.strptime(m.group(2), "%B %d, %Y").date()
    local = pd.Timestamp(datetime.combine(d, t)).tz_localize("America/New_York")
    revision = bool(re.search(r"\b(reissued|corrected|revised)\b", text, re.I))
    return {"embargo_date": d.isoformat(), "embargo_time": t.strftime("%H:%M:%S"),
            "embargo_timezone": "America/New_York",
            "embargo_until_utc": local.tz_convert("UTC").isoformat(),
            "timestamp_source": "release_embargo_text",
            "timestamp_confidence": "high_documented",
            "time_type": "official_embargo_until",
            "revision_mentioned": revision}



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
    if not event.get("publication_time"):
        return pd.NaT
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


def load_offline(offline_dir: Path):
    """Import manually browser-saved official archive HTML, with validation."""
    manifest = json.loads((offline_dir / "manifest.json").read_text(encoding="utf-8"))
    events = []
    sources = {}
    for item in manifest.get("files", []):
        url = item["url"]
        host = urlparse(url).hostname
        if host not in ("www.bls.gov", "www.federalreserve.gov"):
            raise ValueError(f"offline source not official: {url}")
        raw = (offline_dir / item["path"]).read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        text = raw.decode("utf-8", errors="replace")
        fam = item["family"]
        parsed = parse_bls(text, fam) if fam in ("cpi", "empsit") else parse_fomc(text)
        for e in parsed:
            e["_source_key"] = "offline"
            e["source_role"] = "offline_manual_official"
        events += parsed
        sources["offline"] = {"url": url, "status": "OFFLINE_IMPORT", "sha256": sha,
                              "role": "offline_manual_official"}
    return events, sources


def build(data_dir: Path, out_dir: Path, offline_dir: Path | None = None):
    out_dir.mkdir(parents=True, exist_ok=True)
    sources = {}
    events = []
    raw = {}
    for key in ("cpi", "empsit"):
        status, text, sha = fetch(SOURCES[key])
        sources[f"{key}_live"] = {"url": SOURCES[key], "status": status, "sha256": sha,
                                  "role": "primary_official_archive"}
        if status == 200:
            parsed = parse_bls(text, key)
            for e in parsed:
                e["_source_key"] = f"{key}_live"
                e["source_role"] = "primary_official_archive"
            events += parsed
        else:
            legacy = LEGACY_SOURCES[key]
            lstatus, ltext, lsha = fetch(legacy)
            sources[f"{key}_legacy"] = {"url": legacy, "status": lstatus, "sha256": lsha,
                                        "role": "legacy_fallback_not_complete"}
            if lstatus == 200:
                parsed = parse_bls(ltext, key)
                if not parsed:
                    parsed = parse_bls_legacy(ltext, key)
                for e in parsed:
                    e["_source_key"] = f"{key}_legacy"
                    e["source_role"] = "legacy_fallback_not_complete"
                events += parsed
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
    if offline_dir is not None:
        oe, os_ = load_offline(offline_dir)
        events += oe
        sources.update(os_)
    dedup = {e["event_id"]: e for e in events}
    events = list(dedup.values())
    retrieved = datetime.now(timezone.utc).isoformat()
    for e in events:
        if e["event_type"] in ("cpi", "empsit"):
            key = e.get("_source_key", e["event_type"])
            e["official_source"] = "BLS"
            href = e.get("_source_href")
            e["official_source_url"] = (urljoin(sources[key]["url"], href) if href
                                        else sources[key]["url"])
            e["reference_period"] = "BLS release period not parsed from archive index"
            e["source_content_sha256"] = sources[key]["sha256"]
            e["hash_scope"] = "official_archive_index_not_release"
            e["source_role"] = e.get("source_role", "unknown")
        else:
            e["official_source"] = "Federal Reserve Board"
            e["official_source_url"] = ("https://www.federalreserve.gov/newsevents/pressreleases/"
                                        f"monetary{pd.Timestamp(e['publication_date']).strftime('%Y%m%d')}a.htm")
            e["reference_period"] = "FOMC statement"
            e["source_content_sha256"] = sources.get("fomc_recent", {}).get("sha256")
            e["hash_scope"] = "official_calendar_or_historical_page"
            e["source_role"] = "official_calendar"
        e["source_retrieved_at_utc"] = retrieved
        if e.get("publication_time"):
            local = pd.Timestamp(f"{e['publication_date']} {e['publication_time']}").tz_localize("America/New_York")
            e["publication_time_utc"] = local.tz_convert("UTC").isoformat()
        else:
            e["publication_time_utc"] = None
    events.sort(key=lambda x: (x["publication_date"], x["event_type"]))
    spy = pd.read_csv(data_dir / "SPY.csv")
    spy["Date"] = pd.to_datetime(spy["Date"], utc=True).dt.tz_convert(None).dt.normalize()
    sessions = pd.DatetimeIndex(sorted(set(spy.Date)))
    sessions = pd.DatetimeIndex([s for s in sessions if pd.Timestamp(START) <= s <= pd.Timestamp(END)])
    cal = xcals.get_calendar("XNYS")
    sessions = pd.DatetimeIndex([s for s in sessions if cal.is_session(s)])
    for e in events:
        s = align(e, sessions)
        e["tradable_session"] = s.date().isoformat() if pd.notna(s) else None
        if not e.get("publication_time"):
            e["alignment_status"] = "DATE_ONLY_NOT_PRECISE"
        else:
            e["alignment_status"] = "ALIGNED" if pd.notna(s) else "NO_SESSION"
    a = audit(events, sessions)
    report = {"start": START, "end": END, "market_data_asof": str(sessions[-1].date()),
              "market_data_cutoff": END,
              "raw_market_max_date": str(pd.to_datetime(spy.Date, utc=True).max().date()),
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
    p.add_argument("--offline-dir", type=Path, default=None,
                   help="directory with manifest.json and browser-saved official HTML")
    a = p.parse_args()
    print(json.dumps(build(a.data_dir, a.output, a.offline_dir), indent=2))
