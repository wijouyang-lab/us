#!/usr/bin/env python3
"""P17.2.8 reproducible identity recovery from P17.2.7 cache + historical crosswalks."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from lxml import html

ET = ZoneInfo("America/New_York")


def cik10(v):
    s = re.sub(r"\.0$", "", str(v)).strip()
    return s.zfill(10) if s.isdigit() else ""


def parse(path: Path):
    root = html.parse(str(path)).getroot()
    ctx = {}
    for c in root.xpath("//*[contains(local-name(),'context')]"):
        ident = c.xpath(".//*[contains(local-name(),'identifier')]/text()")
        dims = []
        for m in c.xpath(".//*[contains(local-name(),'explicitmember')]"):
            dims.append((m.get("dimension", ""), (m.text or "").strip()))
        for m in c.xpath(".//*[contains(local-name(),'typedmember')]"):
            dims.append((m.get("dimension", ""), "TYPED"))
        ctx[c.get("id")] = {"cik": cik10(ident[0]) if ident else "", "dims": dims}
    facts = []
    for el in root.xpath("//*[contains(local-name(),'nonnumeric')]"):
        qn = el.get("name") or ""
        local = qn.split(":")[-1]
        if local in {"TradingSymbol", "Security12bTitle", "Security12gTitle", "SecurityExchangeName", "EntityCentralIndexKey", "NoTradingSymbolFlag"}:
            facts.append({"tag": local, "qname": qn, "value": re.sub(r"\s+", " ", el.text or "").strip(), "ctx": el.get("contextRef") or el.get("contextref") or ""})
    return ctx, facts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--p27", type=Path, default=Path("../_us_p1727/data/research/p17_2_7"))
    ap.add_argument("--sample", type=Path, default=Path("../_us_p1726/data/research/p17_2_6/p17_2_6_sample_manifest.csv"))
    ap.add_argument("--p390", type=Path, default=Path("../_us_p1721/data/research/p17_1/p17_1_p390_identity_reconciliation.csv"))
    ap.add_argument("--p10", type=Path, default=Path("../_us_audit/p10/data/research/p10_5_2_verified_identity_crosswalk.csv"))
    ap.add_argument("--out", type=Path, default=Path("data/research/p17_2_8"))
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    sample = pd.read_csv(a.sample, dtype=str)
    sel = pd.read_csv(a.p27 / "p17_2_7_selected_filings.csv", dtype=str)
    sel["anchor_date"] = pd.to_datetime(sel.anchor_date)
    # Historical candidates.
    cand = []
    for _, r in sel.iterrows():
        if pd.notna(r.cik) and str(r.cik).strip():
            cand.append({"anchor": r.anchor, "anchor_date": r.anchor_date, "ticker": r.ticker, "candidate_cik": cik10(r.cik), "evidence_source": "CURRENT_COMPANYFACTS"})
    if a.p390.exists():
        p390 = pd.read_csv(a.p390, dtype=str)
        for _, r in p390.iterrows():
            if pd.isna(r.get("cik")): continue
            for _, s in sample[sample.ticker == r.ticker].iterrows():
                cand.append({"anchor": s.anchor, "anchor_date": s.anchor_date, "ticker": s.ticker, "candidate_cik": cik10(r.cik), "evidence_source": "PR390_HISTORICAL_CROSSWALK"})
    if a.p10.exists():
        p10 = pd.read_csv(a.p10, dtype=str)
        for _, r in p10.iterrows():
            if pd.isna(r.get("v2_ciks")): continue
            for _, s in sample[sample.ticker == r.ticker].iterrows():
                cand.append({"anchor": s.anchor, "anchor_date": s.anchor_date, "ticker": s.ticker, "candidate_cik": cik10(r.v2_ciks), "evidence_source": "P10_HISTORICAL_CROSSWALK"})
    cdf = pd.DataFrame(cand).drop_duplicates()
    cdf.to_csv(a.out / "p17_2_8_historical_cik_candidates.csv", index=False)

    # Reparse cached documents.
    cache = a.p27 / "cache"
    facts_rows = []; ctx_rows = []; mapping = []; results = []
    for _, r in sel.iterrows():
        cutoff = pd.Timestamp(r.anchor_date).tz_localize(ET).replace(hour=16).tz_convert("UTC")
        url = f"https://www.sec.gov/Archives/edgar/data/{int(float(r.cik))}/{str(r.accession).replace('-', '')}/{r.primary}" if pd.notna(r.cik) and pd.notna(r.accession) else ""
        path = cache / hashlib.sha256(url.encode()).hexdigest() if url else None
        title = ""; ctx_id = ""; status = "NO_HISTORICAL_CIK_CANDIDATE"; matched = 0
        if path and path.exists():
            ctx, facts = parse(path); digest = hashlib.sha256(path.read_bytes()).hexdigest()
            byctx = {}
            for f in facts:
                byctx.setdefault(f["ctx"], {}).setdefault(f["tag"], []).append(f["value"])
                facts_rows.append({"ticker": r.ticker, "accession": r.accession, "tag": f["tag"], "qname": f["qname"], "value": f["value"], "context_id": f["ctx"], "document_sha256": digest})
            for cid, vals in ctx.items():
                ctx_rows.append({"accession": r.accession, "context_id": cid, "entity_cik": vals["cik"], "dimensions": ";".join(f"{x}={y}" for x, y in vals["dims"])})
            hits = [(cid, vals) for cid, vals in byctx.items() if r.ticker in vals.get("TradingSymbol", [])]
            matched = len(hits)
            if hits:
                cid, vals = hits[0]
                titles = vals.get("Security12bTitle") or vals.get("Security12gTitle") or [""]
                title = titles[0]
                ctx_id = cid
                status = "VERIFIED_FILING_POINT" if title else "SECURITY_CONTEXT_MISMATCH"
                mapping.append({"ticker": r.ticker, "accession": r.accession, "issuer_cik": ctx[cid]["cik"], "security_title": title,
                                "exchange": (vals.get("SecurityExchangeName") or [""])[0], "context_id": cid})
            else:
                status = "SECURITY_CONTEXT_MISMATCH"
        results.append({**r.to_dict(), "security_title": title, "context_id": ctx_id, "identity_status": status,
                        "anchor_cutoff_utc": cutoff.isoformat(), "matched_contexts": matched})
    res = pd.DataFrame(results)
    res["acceptance_utc"] = pd.to_datetime(res.acceptance_utc, errors="coerce", utc=True)
    res["evidence_age_days"] = (pd.to_datetime(res.anchor_cutoff_utc, utc=True) - res.acceptance_utc).dt.total_seconds() / 86400
    res["support_status"] = "NO_HISTORICAL_FILING"
    res.loc[res.identity_status == "VERIFIED_FILING_POINT", "support_status"] = "RECENT_PRIOR_POINT_SUPPORT"
    res.loc[(res.identity_status == "VERIFIED_FILING_POINT") & (res.evidence_age_days > 400), "support_status"] = "STALE_PRIOR_POINT"
    res.to_csv(a.out / "p17_2_8_anchor_identity_results.csv", index=False)
    pd.DataFrame(facts_rows).to_csv(a.out / "p17_2_8_reparsed_xbrl_facts.csv", index=False)
    pd.DataFrame(ctx_rows).to_csv(a.out / "p17_2_8_context_registry.csv", index=False)
    pd.DataFrame(mapping).to_csv(a.out / "p17_2_8_ticker_security_mapping.csv", index=False)
    res[res.support_status == "STALE_PRIOR_POINT"].to_csv(a.out / "p17_2_8_stale_evidence_audit.csv", index=False)
    res[res.evidence_age_days < 0].to_csv(a.out / "p17_2_8_future_evidence_audit.csv", index=False)
    res.to_csv(a.out / "p17_2_8_acceptance_cutoff_audit.csv", index=False)
    # 19 exception rows.
    exc = res[(res.identity_status != "VERIFIED_FILING_POINT") & (res.accession.notna()) & (res.accession != "")].copy()
    exc["failure_reason"] = exc.identity_status
    exc.to_csv(a.out / "p17_2_8_19_filing_exception_reconciliation.csv", index=False)
    # Missing current CIK.
    current = set(cdf[cdf.evidence_source == "CURRENT_COMPANYFACTS"].ticker)
    miss = sample[~sample.ticker.isin(current)].copy()
    miss["pr390_candidate"] = miss.ticker.map(lambda t: ";".join(cdf[(cdf.ticker == t) & (cdf.evidence_source == "PR390_HISTORICAL_CROSSWALK")].candidate_cik.unique()))
    miss["p10_candidate"] = miss.ticker.map(lambda t: ";".join(cdf[(cdf.ticker == t) & (cdf.evidence_source == "P10_HISTORICAL_CROSSWALK")].candidate_cik.unique()))
    miss.to_csv(a.out / "p17_2_8_missing_cik_reconciliation.csv", index=False)
    anchor = res.groupby(["anchor", "anchor_date"]).agg(sampled=("ticker", "size"),
        cik_candidates=("cik", lambda x: sum(1 for v in x if pd.notna(v) and str(v) != "")),
        filings=("accession", lambda x: sum(1 for v in x if pd.notna(v) and str(v) != "")),
        verified=("identity_status", lambda x: (x == "VERIFIED_FILING_POINT").sum()),
        stale=("support_status", lambda x: (x == "STALE_PRIOR_POINT").sum()),
        unresolved=("identity_status", lambda x: (x != "VERIFIED_FILING_POINT").sum())).reset_index()
    anchor.to_csv(a.out / "p17_2_8_anchor_coverage.csv", index=False)
    summary = {"samples": len(res), "unique_tickers": res.ticker.nunique(),
               "historical_candidate_rows": len(cdf), "unique_candidate_ciks": cdf.candidate_cik.nunique(),
               "current_cik_tickers": len(current), "missing_current_cik_rows": len(miss),
               "pr390_recoverable_rows": int((miss.pr390_candidate != "").sum()),
               "p10_recoverable_rows": int((miss.p10_candidate != "").sum()),
               "verified_points": int((res.identity_status == "VERIFIED_FILING_POINT").sum()),
               "exceptions": len(exc), "stale": int((res.support_status == "STALE_PRIOR_POINT").sum()),
               "future": int((res.evidence_age_days < 0).sum()), "anchor": anchor.to_dict("records"),
               "network_requests": 0, "cache_documents": len(list(cache.glob("*"))),
               "status": "PARTIAL_COVERAGE_ONLY"}
    (a.out / "p17_2_8_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    files = {}
    for p in a.out.iterdir():
        if p.suffix in {".csv", ".json"}:
            files[p.name] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
    (a.out / "p17_2_8_manifest.json").write_text(json.dumps({"outputs": files}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
