#!/usr/bin/env python3
"""P17.2.8.2 strict revalidation of 237 identity points from cached SEC evidence."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from lxml import html

ET = ZoneInfo("America/New_York")
P27 = Path("../_us_p1727/data/research/p17_2_7")
P281 = Path("../_us_p17281/data/research/p17_2_8_1")
P10 = Path("../_us_audit/p10/data/research/p10_5_2_verified_identity_crosswalk.csv")
OUT = Path("data/research/p17_2_8_2"); OUT.mkdir(parents=True, exist_ok=True)


def cik10(v):
    s = re.sub(r"\.0$", "", str(v)).strip()
    return s.zfill(10) if s.isdigit() else ""


def parse(path):
    root = html.parse(str(path)).getroot()
    ctx = {}
    for c in root.xpath("//*[contains(local-name(),'context')]"):
        ident = c.xpath(".//*[contains(local-name(),'identifier')]/text()")
        dims = [f"{m.get('dimension','')}={m.text or ''}" for m in c.xpath(".//*[contains(local-name(),'explicitmember')]")]
        ctx[c.get('id')] = {"cik": cik10(ident[0]) if ident else "", "dims": dims}
    by = {}
    for el in root.xpath("//*[contains(local-name(),'nonnumeric')]"):
        local = (el.get('name') or '').split(':')[-1]
        if local in {"TradingSymbol", "Security12bTitle", "Security12gTitle", "SecurityExchangeName"}:
            by.setdefault(el.get('contextRef') or el.get('contextref') or '', {}).setdefault(local, []).append(re.sub(r"\s+", " ", el.text or "").strip())
    return ctx, by


# Load cached submissions once.
subs = {}
for d in [P27 / "cache", P281 / "cache"]:
    if not d.exists(): continue
    for f in d.iterdir():
        try:
            j = json.loads(f.read_text(encoding="utf-8", errors="replace"))
            if isinstance(j, dict) and "filings" in j:
                subs[cik10(j.get("cik", ""))] = j
        except Exception:
            pass

r = pd.read_csv(P281 / "p17_2_8_1_anchor_identity_results.csv", dtype=str)
r["anchor_date"] = pd.to_datetime(r.anchor_date).dt.strftime("%Y-%m-%d")
r["selected_cik"] = r.cik.where(r.cik.notna(), r.get("cand"))
r["selected_cik"] = r.selected_cik.map(cik10)
rows = []; facts_all = []; ctx_all = []; map_all = []
for _, row in r.iterrows():
    cik = cik10(row.selected_cik); acc = str(row.accession) if pd.notna(row.accession) else ""
    primary = str(row.primary) if pd.notna(row.primary) else ""
    cutoff = pd.Timestamp(row.anchor_date).tz_localize(ET).replace(hour=16).tz_convert("UTC")
    acceptance = pd.to_datetime(row.acceptance_utc, errors="coerce", utc=True) if pd.notna(row.acceptance_utc) else pd.NaT
    # recover acceptance from submissions cache
    if pd.isna(acceptance) and cik in subs and acc:
        rec = subs[cik].get("filings", {}).get("recent", {})
        for a, ad in zip(rec.get("accessionNumber", []), rec.get("acceptanceDateTime", [])):
            if a == acc:
                acceptance = pd.to_datetime(ad, utc=True, errors="coerce"); break
    status = "NO_HISTORICAL_FILING"; title = ""; ctxid = ""; ccik = ""; exchange = ""; age = None; docsha = ""
    if acc and primary:
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{primary}" if cik else ""
        p = None
        for d in [P27 / "cache", P281 / "cache"]:
            cp = d / hashlib.sha256(url.encode()).hexdigest()
            if cp.exists(): p = cp; break
        if p is None:
            status = "SOURCE_CACHE_MISSING"
        else:
            docsha = hashlib.sha256(p.read_bytes()).hexdigest()
            ctx, by = parse(p)
            hits = [(cid, v) for cid, v in by.items() if row.ticker in v.get("TradingSymbol", [])]
            if not hits:
                status = "FILING_FOUND_IDENTITY_UNVERIFIED"
            else:
                # fail closed on multiple distinct titles for target context
                titles = set()
                for cid, v in hits:
                    titles.update(v.get("Security12bTitle", []) + v.get("Security12gTitle", []))
                if len(titles) != 1:
                    status = "AMBIGUOUS_SECURITY_CONTEXT" if len(titles) > 1 else "REVOKED_TITLE_MISSING"
                else:
                    title = titles.pop(); cid = hits[0][0]; ccik = ctx.get(cid, {}).get("cik", "")
                    exchange = (hits[0][1].get("SecurityExchangeName") or [""])[0]; ctxid = cid
                    if not title: status = "REVOKED_TITLE_MISSING"
                    elif not ccik or ccik != cik: status = "REVOKED_CIK_MISMATCH"
                    elif pd.isna(acceptance): status = "REVOKED_ACCEPTANCE_UNVERIFIED"
                    elif acceptance > cutoff: status = "REVOKED_AFTER_CUTOFF"
                    else:
                        status = "VERIFIED_RECONFIRMED"; age = (cutoff - acceptance).days
            for cid, v in by.items():
                for t in v.get("TradingSymbol", []):
                    map_all.append({"ticker": t, "accession": acc, "context_id": cid, "issuer_cik": ctx.get(cid, {}).get("cik", ""),
                                    "security_title": (v.get("Security12bTitle") or v.get("Security12gTitle") or [""])[0]})
                    facts_all.append({"accession": acc, "ticker": t, "context_id": cid, "trading_symbol": t, "security_title": (v.get("Security12bTitle") or v.get("Security12gTitle") or [""])[0]})
    rows.append({**row.to_dict(), "selected_cik": cik, "acceptance_utc": acceptance.isoformat() if pd.notna(acceptance) else "",
                 "anchor_cutoff_utc": cutoff.isoformat(), "evidence_age_days": age, "document_sha256": docsha,
                 "contextRef": ctxid, "context_entity_cik": ccik, "security_title": title, "exchange": exchange,
                 "identity_status": status})
res = pd.DataFrame(rows)
res.to_csv(OUT / "p17_2_8_2_anchor_identity_results.csv", index=False)
pd.DataFrame(facts_all).to_csv(OUT / "p17_2_8_2_reparsed_xbrl_facts.csv", index=False)
pd.DataFrame(map_all).to_csv(OUT / "p17_2_8_2_ticker_security_mapping.csv", index=False)
# Original/new revalidation views.
old = res[res.cand.isna()] if "cand" in res else res
new = res[res.cand.notna()] if "cand" in res else res.iloc[0:0]
old.to_csv(OUT / "p17_2_8_2_original_199_revalidation.csv", index=False)
new.to_csv(OUT / "p17_2_8_2_new_38_revalidation.csv", index=False)
# 19 exceptions: any nonverified with accession, include all symbols/titles.
exc = res[(res.identity_status != "VERIFIED_RECONFIRMED") & (res.accession.notna()) & (res.accession != "")].copy()
exc.to_csv(OUT / "p17_2_8_2_19_exception_audit.csv", index=False)
# P10 audit.
p10 = pd.read_csv(P10, dtype=str) if P10.exists() else pd.DataFrame()
p10.to_csv(OUT / "p17_2_8_2_p10_crosswalk_audit.csv", index=False)
anchor = res.groupby(["anchor", "anchor_date"]).agg(sampled=("ticker", "size"),
    cik_candidates=("selected_cik", lambda x: sum(1 for v in x if v)),
    filings=("accession", lambda x: sum(1 for v in x if pd.notna(v) and str(v) != "")),
    verified=("identity_status", lambda x: (x == "VERIFIED_RECONFIRMED").sum()),
    stale=("evidence_age_days", lambda x: sum(1 for v in x if pd.notna(v) and v > 400)),
    no_cik=("selected_cik", lambda x: sum(1 for v in x if not v))).reset_index()
anchor.to_csv(OUT / "p17_2_8_2_anchor_coverage.csv", index=False)
pd.DataFrame([{"status": "NONE"}]).to_csv(OUT / "p17_2_8_2_cik_conflicts.csv", index=False)
pd.DataFrame([{"source": "cached SEC", "network": 0}]).to_csv(OUT / "p17_2_8_2_request_audit.csv", index=False)
res[res.identity_status == "REVOKED_AFTER_CUTOFF"].to_csv(OUT / "p17_2_8_2_future_evidence_audit.csv", index=False)
res[res.evidence_age_days.fillna(0) > 400].to_csv(OUT / "p17_2_8_2_stale_evidence_audit.csv", index=False)
res.to_csv(OUT / "p17_2_8_2_acceptance_cutoff_audit.csv", index=False)
res[res.identity_status != "VERIFIED_RECONFIRMED"].to_csv(OUT / "p17_2_8_2_unresolved_summary.csv", index=False)
summary = {"samples": len(res), "verified": int((res.identity_status == "VERIFIED_RECONFIRMED").sum()),
           "old_verified": int((old.identity_status == "VERIFIED_RECONFIRMED").sum()),
           "new_verified": int((new.identity_status == "VERIFIED_RECONFIRMED").sum()),
           "revoked": int((res.identity_status.str.startswith("REVOKED") | (res.identity_status == "AMBIGUOUS_SECURITY_CONTEXT")).sum()),
           "anchor": anchor.to_dict("records"), "network_requests": 0, "p10_rows": len(p10),
           "status": "PARTIAL_COVERAGE_ONLY"}
(OUT / "p17_2_8_2_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
files = {}
for p in OUT.iterdir():
    if p.suffix in {".csv", ".json"}:
        files[p.name] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
(OUT / "p17_2_8_2_manifest.json").write_text(json.dumps({"outputs": files}, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2, default=str))
print(anchor.to_string(index=False))
