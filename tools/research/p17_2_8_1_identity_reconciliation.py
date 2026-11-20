#!/usr/bin/env python3
"""P17.2.8.1 PR390 historical CIK recovery and reproducible replay."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from lxml import html

ET = ZoneInfo("America/New_York")


def cik10(v):
    s = re.sub(r"\.0$", "", str(v)).strip()
    return s.zfill(10) if s.isdigit() else ""


def parse(path):
    root = html.parse(str(path)).getroot()
    ctx = {}; facts = []
    for c in root.xpath("//*[contains(local-name(),'context')]"):
        ident = c.xpath(".//*[contains(local-name(),'identifier')]/text()")
        dims = []
        for m in c.xpath(".//*[contains(local-name(),'explicitmember')]"):
            dims.append(f"{m.get('dimension','')}={m.text or ''}")
        for m in c.xpath(".//*[contains(local-name(),'typedmember')]"):
            dims.append(f"{m.get('dimension','')}=TYPED:{''.join(m.itertext())}")
        ctx[c.get('id')] = {"cik": cik10(ident[0]) if ident else "", "dims": dims}
    for el in root.xpath("//*[contains(local-name(),'nonnumeric')]"):
        q = el.get("name") or ""; local = q.split(":")[-1]
        if local in {"TradingSymbol", "Security12bTitle", "Security12gTitle", "SecurityExchangeName"}:
            facts.append({"tag": local, "qname": q, "value": re.sub(r"\s+", " ", el.text or "").strip(), "ctx": el.get("contextRef") or ""})
    return ctx, facts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=Path, default=Path("../_us_p1726/data/research/p17_2_6/p17_2_6_sample_manifest.csv"))
    ap.add_argument("--p27", type=Path, default=Path("../_us_p1727/data/research/p17_2_7"))
    ap.add_argument("--p390", type=Path, default=Path("../_us_p171/data/research/p17_1/p17_1_p390_identity_reconciliation.csv"))
    ap.add_argument("--out", type=Path, default=Path("data/research/p17_2_8_1"))
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    cache = a.out / "cache"; cache.mkdir(exist_ok=True)
    sample = pd.read_csv(a.sample, dtype=str)
    p390 = pd.read_csv(a.p390, dtype=str)
    p390["cand"] = p390["candidate_cik"].where(p390.candidate_cik.notna(), p390.cik).astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(10)
    miss = sample[sample.cik_candidate.isna()].copy()
    joined = miss.merge(p390[["ticker", "cand", "identity_confidence", "company_name", "event_type", "announcement_available_date"]], on="ticker", how="inner", suffixes=("", "_p390"))
    joined.to_csv(a.out / "p17_2_8_1_historical_cik_candidates.csv", index=False)
    # Current P17.2.7 results for 233 samples.
    res = pd.read_csv(a.p27 / "p17_2_7_anchor_identity_results.csv", dtype=str)
    res["anchor_date"] = pd.to_datetime(res.anchor_date)
    # New retrieval for PR390 samples.
    HEAD = {"User-Agent": os.environ.get("SEC_USER_AGENT", "").strip()}
    if not HEAD["User-Agent"]:
        raise SystemExit("SEC_USER_AGENT missing")
    audit = []; net = 0

    def fetch(url):
        nonlocal net
        key = cache / hashlib.sha256(url.encode()).hexdigest()
        if key.exists():
            audit.append({"url": url, "status": "CACHE_HIT", "bytes": key.stat().st_size, "sha256": hashlib.sha256(key.read_bytes()).hexdigest()})
            return key.read_bytes()
        if net >= 150:
            raise RuntimeError("REQUEST_BUDGET_EXCEEDED")
        r = requests.get(url, headers=HEAD, timeout=45); net += 1
        if r.status_code == 200:
            key.write_bytes(r.content)
            audit.append({"url": url, "status": "NETWORK_200", "bytes": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()})
            time.sleep(1)
            return r.content
        audit.append({"url": url, "status": "NETWORK_ERROR", "code": r.status_code})
        if r.status_code == 403: raise RuntimeError("HTTP_403_STOP")
        return None

    subs = {}; newrows = []; docs = {}
    for cik in sorted(set(joined.cand)):
        try:
            b = fetch(f"https://data.sec.gov/submissions/CIK{cik}.json")
            if b: subs[cik] = json.loads(b)
        except Exception:
            continue
    for _, r in joined.iterrows():
        cutoff = pd.Timestamp(r.anchor_date).tz_localize(ET).replace(hour=16).tz_convert("UTC")
        rec = subs.get(r.cand, {}).get("filings", {}).get("recent", {})
        pick = None
        for form, acc, fd, ad, doc in zip(rec.get("form", []), rec.get("accessionNumber", []), rec.get("filingDate", []), rec.get("acceptanceDateTime", []), rec.get("primaryDocument", [])):
            if form not in ("10-K", "10-Q"): continue
            at = pd.to_datetime(ad, utc=True, errors="coerce")
            if pd.isna(at) or at > cutoff: continue
            if pick is None or at > pick["acceptance"]:
                pick = {"form": form, "accession": acc, "filing_date": fd, "acceptance": at, "primary": doc}
        if not pick:
            newrows.append({**r.to_dict(), "identity_status": "NO_PRIOR_FILING", "security_title": "", "accession": ""}); continue
        docs[pick["accession"]] = (r.cand, pick)
        newrows.append({**r.to_dict(), "form": pick["form"], "accession": pick["accession"], "primary": pick["primary"],
                        "acceptance_utc": pick["acceptance"].isoformat(), "identity_status": "FILING_FOUND_IDENTITY_UNVERIFIED",
                        "security_title": "", "anchor_cutoff_utc": cutoff.isoformat()})
    # Parse docs.
    mrows = []; facts_rows = []
    for acc, (cik, pick) in docs.items():
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{pick['primary']}"
        try:
            b = fetch(url)
            if not b: continue
            path = cache / hashlib.sha256(url.encode()).hexdigest()
            ctx, facts = parse(path); by = {}
            for f in facts: by.setdefault(f["ctx"], {}).setdefault(f["tag"], []).append(f["value"])
            for t in [x for v in by.values() for x in v.get("TradingSymbol", [])]:
                mrows.append({"ticker": t, "accession": acc, "issuer_cik": next((v["cik"] for v in ctx.values() if v["cik"]), ""),
                              "security_title": next((v["Security12bTitle"][0] for v in by.values() if t in v.get("TradingSymbol", []) and v.get("Security12bTitle")), "")})
        except Exception:
            pass
    md = pd.DataFrame(mrows)
    # Update new rows by exact ticker/accession.
    for i, r in enumerate(newrows):
        if not r.get("accession"): continue
        h = md[(md.accession == r["accession"]) & (md.ticker == r["ticker"])] if len(md) else md
        if len(h):
            newrows[i]["identity_status"] = "VERIFIED_FILING_POINT"
            newrows[i]["security_title"] = h.security_title.iloc[0]
    nd = pd.DataFrame(newrows)
    # Full 300: old verified results + recovered rows.
    keep = res[~res.ticker.isin(nd.ticker)].copy()
    combined = pd.concat([keep, nd], ignore_index=True, sort=False)
    combined["acceptance_utc"] = pd.to_datetime(combined.acceptance_utc, errors="coerce", utc=True)
    combined["anchor_cutoff_utc"] = pd.to_datetime(combined.anchor_cutoff_utc, errors="coerce", utc=True)
    combined["evidence_age_days"] = (combined.anchor_cutoff_utc - combined.acceptance_utc).dt.total_seconds() / 86400
    combined.to_csv(a.out / "p17_2_8_1_anchor_identity_results.csv", index=False)
    pd.DataFrame(audit).to_csv(a.out / "p17_2_8_1_request_audit.csv", index=False)
    # Exceptions: existing 19 from P17.2.7.
    exc = res[(res.identity_status != "VERIFIED_FILING_POINT") & (res.accession.notna()) & (res.accession != "")]
    exc.to_csv(a.out / "p17_2_8_1_19_exception_reconciliation.csv", index=False)
    # Anchors.
    anchor = combined.groupby(["anchor", "anchor_date"]).agg(sampled=("ticker", "size"),
        cik_candidates=("cik", lambda x: sum(1 for v in x if pd.notna(v) and str(v) != "")),
        filings=("accession", lambda x: sum(1 for v in x if pd.notna(v) and str(v) != "")),
        verified=("identity_status", lambda x: (x == "VERIFIED_FILING_POINT").sum())).reset_index()
    anchor.to_csv(a.out / "p17_2_8_1_anchor_coverage.csv", index=False)
    summary = {"pr390_rows": len(p390), "missing_current_rows": len(miss), "overlap_rows": len(joined), "overlap_tickers": joined.ticker.nunique(),
               "pr390_high_rows": int((joined.identity_confidence == "high").sum()), "pr390_medium_rows": int((joined.identity_confidence == "medium").sum()),
               "recovered_verified": int((nd.identity_status == "VERIFIED_FILING_POINT").sum()),
               "network_requests": net, "cache_hits": sum(1 for x in audit if x["status"] == "CACHE_HIT"),
               "anchor": anchor.to_dict("records"), "status": "PARTIAL_COVERAGE_ONLY"}
    (a.out / "p17_2_8_1_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    files = {}
    for p in a.out.iterdir():
        if p.suffix in {".csv", ".json"}:
            files[p.name] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
    (a.out / "p17_2_8_1_manifest.json").write_text(json.dumps({"outputs": files}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
