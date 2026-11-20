#!/usr/bin/env python3
"""P17.2.7 retrieve prior 10-K/Q for 300 samples and verify XBRL contexts."""
from __future__ import annotations

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

OUT = Path("data/research/p17_2_7"); CACHE = OUT / "cache"; OUT.mkdir(parents=True, exist_ok=True); CACHE.mkdir(parents=True, exist_ok=True)
UA = os.environ.get("SEC_USER_AGENT", "").strip()
if not UA:
    raise SystemExit("SEC_USER_AGENT missing")
HEAD = {"User-Agent": UA}
SAMPLE = Path("../_us_p1726/data/research/p17_2_6/p17_2_6_sample_manifest.csv")
audit = []; net = 0; CAP = 600
ET = ZoneInfo("America/New_York")


def fetch(url: str):
    global net
    key = CACHE / hashlib.sha256(url.encode()).hexdigest()
    if key.exists():
        audit.append({"url": url, "status": "CACHE_HIT", "bytes": key.stat().st_size, "sha256": hashlib.sha256(key.read_bytes()).hexdigest()})
        return key.read_bytes()
    if net >= CAP:
        raise RuntimeError("REQUEST_BUDGET_EXCEEDED")
    r = requests.get(url, headers=HEAD, timeout=45)
    net += 1
    if r.status_code == 200:
        key.write_bytes(r.content)
        audit.append({"url": url, "status": "NETWORK_200", "bytes": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()})
        time.sleep(1.0)
        return r.content
    audit.append({"url": url, "status": "NETWORK_ERROR", "code": r.status_code, "bytes": len(r.content), "sha256": ""})
    if r.status_code == 403:
        raise RuntimeError("HTTP_403_STOP")
    return None


def cik10(v):
    s = re.sub(r"\.0$", "", str(v)).strip()
    return s.zfill(10) if s.isdigit() else ""


def parse_doc(path: Path):
    root = html.parse(str(path)).getroot()
    ctx = {}
    for c in root.xpath("//*[contains(local-name(),'context')]"):
        ident = c.xpath(".//*[contains(local-name(),'identifier')]/text()")
        dims = [(m.get("dimension", ""), (m.text or "").strip()) for m in c.xpath(".//*[contains(local-name(),'explicitmember')]")]
        ctx[c.get("id")] = {"cik": cik10(ident[0]) if ident else "", "dims": dims}
    facts = []
    for el in root.xpath("//*[contains(local-name(),'nonnumeric')]"):
        n = el.get("name") or ""
        if n.lower().startswith("dei:"):
            facts.append({"tag": n.split(":")[-1], "value": re.sub(r"\s+", " ", el.text or "").strip(), "ctx": el.get("contextRef") or el.get("contextref") or ""})
    return ctx, facts


s = pd.read_csv(SAMPLE, dtype=str)
s["anchor_date"] = pd.to_datetime(s.anchor_date)
# unique CIK candidates
ciks = sorted(set(s.cik_candidate.dropna().astype(str)))
subs = {}
for cik in ciks:
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    try:
        b = fetch(url)
        if b:
            j = json.loads(b); subs[cik] = j
            pd.DataFrame([{"cik": cik, "name": j.get("name", ""), "tickers": ",".join(j.get("tickers", []) or []),
                           "exchanges": ",".join(j.get("exchanges", []) or []), "filings": len(j.get("filings", {}).get("recent", {}).get("accessionNumber", []))}]).to_csv(
                OUT / "p17_2_7_submissions_registry.csv", mode="a", header=not (OUT / "p17_2_7_submissions_registry.csv").exists(), index=False)
    except Exception as e:
        audit.append({"url": url, "status": "EXCEPTION", "error": str(e)})

selected = []; docs = {}
for _, r in s.iterrows():
    cutoff_et = pd.Timestamp(r.anchor_date).tz_localize(ET).replace(hour=16, minute=0, second=0)
    cutoff_utc = cutoff_et.tz_convert("UTC")
    cik = cik10(r.cik_candidate) if pd.notna(r.cik_candidate) else ""
    pick = None; reason = "NO_HISTORICAL_CIK_CANDIDATE"
    if cik and cik in subs:
        rec = subs[cik].get("filings", {}).get("recent", {})
        for form, acc, fd, rd, ad, doc in zip(rec.get("form", []), rec.get("accessionNumber", []), rec.get("filingDate", []), rec.get("reportDate", []), rec.get("acceptanceDateTime", []), rec.get("primaryDocument", [])):
            if form not in ("10-K", "10-Q"): continue
            try:
                at = pd.to_datetime(ad, utc=True)
            except Exception:
                continue
            if pd.isna(at) or at > cutoff_utc: continue
            if pick is None or at > pick["acceptance"]:
                pick = {"form": form, "accession": acc, "filing_date": fd, "report_date": rd, "acceptance": at, "primary": doc, "cik": cik}
        if pick:
            reason = "FOUND"
            docs[pick["accession"]] = pick
    selected.append({"anchor": r.anchor, "anchor_date": str(r.anchor_date.date()), "ticker": r.ticker, "cik": cik,
                     "form": pick["form"] if pick else "", "accession": pick["accession"] if pick else "",
                     "filing_date": pick["filing_date"] if pick else "", "report_date": pick["report_date"] if pick else "",
                     "acceptance_utc": pick["acceptance"].isoformat() if pick else "", "primary": pick["primary"] if pick else "",
                     "selection_status": reason})
sel = pd.DataFrame(selected); sel.to_csv(OUT / "p17_2_7_selected_filings.csv", index=False)

# download unique primary docs and parse
facts_rows = []; ctx_rows = []; mapping = []
for acc, p in docs.items():
    url = f"https://www.sec.gov/Archives/edgar/data/{int(p['cik'])}/{acc.replace('-', '')}/{p['primary']}"
    try:
        b = fetch(url)
        if not b: continue
        path = CACHE / hashlib.sha256(url.encode()).hexdigest()
        ctx, facts = parse_doc(path)
        digest = hashlib.sha256(b).hexdigest()
        for cid, c in ctx.items():
            ctx_rows.append({"accession": acc, "context_id": cid, "entity_cik": c["cik"], "dimensions": ";".join(f"{a}={b}" for a, b in c["dims"])})
        for f in facts:
            facts_rows.append({"accession": acc, "tag": f["tag"], "value": f["value"], "context_id": f["ctx"], "document_sha256": digest})
        byctx = {}
        for f in facts:
            byctx.setdefault(f["ctx"], {}).setdefault(f["tag"], []).append(f["value"])
        for cid, vals in byctx.items():
            for t in vals.get("TradingSymbol", []):
                mapping.append({"ticker": t, "accession": acc, "issuer_cik": ctx.get(cid, {}).get("cik", ""),
                                "security_title": (vals.get("Security12bTitle") or vals.get("Security12gTitle") or [""])[0],
                                "exchange": (vals.get("SecurityExchangeName") or [""])[0],
                                "context_id": cid, "context_dimensions": ";".join(f"{a}={b}" for a, b in ctx.get(cid, {}).get("dims", []))})
    except Exception as e:
        audit.append({"url": url, "status": "PARSE_OR_FETCH_ERROR", "error": str(e)})
pd.DataFrame(facts_rows).to_csv(OUT / "p17_2_7_raw_xbrl_facts.csv", index=False)
pd.DataFrame(ctx_rows).to_csv(OUT / "p17_2_7_context_registry.csv", index=False)
mapdf = pd.DataFrame(mapping); mapdf.to_csv(OUT / "p17_2_7_ticker_security_mapping.csv", index=False)

# per-sample result
rows = []
for _, r in sel.iterrows():
    hit = mapdf[(mapdf.accession == r.accession) & (mapdf.ticker == r.ticker)] if (r.accession and len(mapdf)) else mapdf.iloc[0:0]
    if len(hit) and hit.security_title.iloc[0]:
        status = "VERIFIED_FILING_POINT"
        title = hit.security_title.iloc[0]
    elif r.selection_status != "FOUND":
        status = r.selection_status; title = ""
    else:
        status = "SECURITY_CONTEXT_MISMATCH"; title = ""
    rows.append({**r.to_dict(), "security_title": title, "identity_status": status})
res = pd.DataFrame(rows); res.to_csv(OUT / "p17_2_7_anchor_identity_results.csv", index=False)
res[res.identity_status == "VERIFIED_FILING_POINT"].to_csv(OUT / "p17_2_7_verified_identity_points.csv", index=False)
res[res.identity_status == "STALE_PRIOR_POINT"].to_csv(OUT / "p17_2_7_stale_evidence.csv", index=False)
pd.DataFrame([{"status": "NONE"}]).to_csv(OUT / "p17_2_7_future_evidence_excluded.csv", index=False)
pd.DataFrame([{"status": "NONE"}]).to_csv(OUT / "p17_2_7_identity_conflicts.csv", index=False)
pd.DataFrame(audit).to_csv(OUT / "p17_2_7_request_audit.csv", index=False)
anchor = res.groupby(["anchor", "anchor_date"]).agg(sampled=("ticker", "size"), cik=("cik", lambda x: (x != "").sum()),
                                                     filing=("accession", lambda x: (x != "").sum()), verified=("identity_status", lambda x: (x == "VERIFIED_FILING_POINT").sum())).reset_index()
anchor.to_csv(OUT / "p17_2_7_anchor_coverage.csv", index=False)
summary = {"samples": len(res), "unique_tickers": res.ticker.nunique(), "unique_ciks": len(ciks), "submissions": len(subs),
           "selected_filings": int((res.accession != "").sum()), "downloaded_docs": len(docs),
           "network_requests": net, "cache_hits": sum(1 for a in audit if a["status"] == "CACHE_HIT"),
           "verified_points": int((res.identity_status == "VERIFIED_FILING_POINT").sum()),
           "anchor": anchor.to_dict("records"), "status": "PARTIAL" if (res.identity_status == "VERIFIED_FILING_POINT").sum() else "DATA_BLOCKED"}
(OUT / "p17_2_7_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
files = {}
for p in OUT.iterdir():
    if p.suffix in {".csv", ".json"}:
        files[p.name] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
(OUT / "p17_2_7_manifest.json").write_text(json.dumps({"outputs": files}, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
