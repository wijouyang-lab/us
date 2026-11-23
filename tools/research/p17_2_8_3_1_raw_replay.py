#!/usr/bin/env python3
"""P17.2.8.3.1 raw Inline XBRL forensic replay, no network."""
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
P27 = Path("../_us_p1727/data/research/p17_2_7")
P281 = Path("../_us_p17281/data/research/p17_2_8_1")
P283 = Path("data/research/p17_2_8_3")
P390 = Path("../_us_p171/data/research/p17_1/p17_1_p390_identity_reconciliation.csv")
P10 = Path("../_us_audit/p10/data/research/p10_5_2_verified_identity_crosswalk.csv")


def cik10(v):
    s = re.sub(r"\.0$", "", str(v)).strip()
    return s.zfill(10) if s.isdigit() else ""


def parse_doc(path: Path):
    root = html.parse(str(path)).getroot()
    ctx = {}
    for c in root.xpath("//*[contains(local-name(),'context')]"):
        cid = c.get("id"); ident = c.xpath(".//*[contains(local-name(),'identifier')]/text()")
        exp = [f"{m.get('dimension','')}={m.text or ''}" for m in c.xpath(".//*[contains(local-name(),'explicitmember')]")]
        typ = [f"{m.get('dimension','')}=TYPED:{''.join(m.itertext())}" for m in c.xpath(".//*[contains(local-name(),'typedmember')]")]
        ps = c.xpath(".//*[contains(local-name(),'startdate')]/text()")
        pe = c.xpath(".//*[contains(local-name(),'enddate')]/text()")
        ins = c.xpath(".//*[contains(local-name(),'instant')]/text()")
        ctx[cid] = {"cik": cik10(ident[0]) if ident else "", "explicit": ";".join(exp), "typed": ";".join(typ),
                    "period_start": ps[0] if ps else "", "period_end": pe[0] if pe else "", "instant": ins[0] if ins else ""}
    by = {}
    for el in root.xpath("//*[contains(local-name(),'nonnumeric')]"):
        qn = el.get("name") or ""; local = qn.split(":")[-1]
        if local in {"TradingSymbol", "Security12bTitle", "Security12gTitle", "SecurityExchangeName", "EntityCentralIndexKey"}:
            by.setdefault(el.get("contextRef") or el.get("contextref") or "", {}).setdefault(local, []).append(re.sub(r"\s+", " ", el.text or "").strip())
    return ctx, by


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists() and any(a.out.iterdir()):
        raise SystemExit("REFUSING_NONEMPTY_OUTPUT")
    a.out.mkdir(parents=True, exist_ok=True)
    res = pd.read_csv(P283 / "p17_2_8_3_anchor_identity_results.csv", dtype=str)
    docs = {}; facts = []; ctxs = []
    doc_status = []
    for _, r in res.iterrows():
        acc = str(r.accession) if pd.notna(r.accession) else ""
        primary = str(r.primary) if pd.notna(r.primary) else ""
        cik = cik10(r.selected_cik) if pd.notna(r.selected_cik) else ""
        if not acc or not primary:
            doc_status.append({"anchor": r.anchor, "ticker": r.ticker, "accession": "", "status": "NO_HISTORICAL_FILING"}); continue
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{primary}"
        path = None
        for d in [P27 / "cache", P281 / "cache"]:
            p = d / hashlib.sha256(url.encode()).hexdigest()
            if p.exists(): path = p; break
        if path is None:
            doc_status.append({"anchor": r.anchor, "ticker": r.ticker, "accession": acc, "status": "SUBMISSION_FOUND_DOCUMENT_MISSING"}); continue
        docs[(r.anchor, r.ticker)] = path
        doc_status.append({"anchor": r.anchor, "ticker": r.ticker, "accession": acc, "status": "RAW_DOCUMENT_FOUND",
                           "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    pd.DataFrame(doc_status).to_csv(a.out / "p17_2_8_3_1_document_registry.csv", index=False)
    rows = []; parse_ok = 0; parse_err = 0
    for _, r in res.iterrows():
        key = (r.anchor, r.ticker); path = docs.get(key)
        status = "NO_HISTORICAL_FILING"; title = ""; ctxid = ""; ccik = ""; age = None; docsha = ""; symbols = ""; titles_all = ""
        if path:
            try:
                ctx, by = parse_doc(path); parse_ok += 1
            except Exception:
                parse_err += 1; ctx = {}; by = {}
            docsha = hashlib.sha256(path.read_bytes()).hexdigest()
            hits = [(cid, v) for cid, v in by.items() if r.ticker in v.get("TradingSymbol", [])]
            symbols = ";".join(sorted({t for v in by.values() for t in v.get("TradingSymbol", [])}))
            if not hits:
                status = "FILING_FOUND_IDENTITY_UNVERIFIED"
            else:
                title_set = set(); empty_ctx = False
                for cid, v in hits:
                    t = [x for x in (v.get("Security12bTitle", []) + v.get("Security12gTitle", [])) if x]
                    if not t: empty_ctx = True
                    title_set.update(t)
                titles_all = ";".join(sorted(title_set))
                if empty_ctx and title_set:
                    status = "AMBIGUOUS_SECURITY_CONTEXT"
                elif len(title_set) == 0:
                    status = "REVOKED_TITLE_MISSING"
                elif len(title_set) > 1:
                    status = "AMBIGUOUS_SECURITY_CONTEXT"
                else:
                    title = title_set.pop(); ctxid = hits[0][0]; ccik = ctx.get(ctxid, {}).get("cik", "")
                    acceptance = pd.to_datetime(r.acceptance_utc, errors="coerce", utc=True)
                    cutoff = pd.Timestamp(r.anchor_date).tz_localize(ET).replace(hour=16).tz_convert("UTC")
                    age = (cutoff - acceptance).days if pd.notna(acceptance) else None
                    if not ccik or ccik != cik10(r.selected_cik): status = "REVOKED_CIK_MISMATCH"
                    elif pd.isna(acceptance): status = "ACCEPTANCE_UNVERIFIED"
                    elif acceptance > cutoff: status = "REVOKED_AFTER_CUTOFF"
                    elif age > 400: status = "STALE_PRIOR_POINT"
                    else: status = "VERIFIED_RECONFIRMED"
        rows.append({**r.to_dict(), "security_title": title, "contextRef": ctxid, "context_entity_cik": ccik,
                     "evidence_age_days": age, "document_sha256": docsha, "all_trading_symbols": symbols,
                     "all_titles": titles_all, "identity_status": status})
        if path:
            ctx, by = parse_doc(path)
            for cid, v in by.items():
                ctxs.append({"accession": r.accession, "context_id": cid, "entity_cik": ctx.get(cid, {}).get("cik", ""),
                             "explicit_dimensions": ctx.get(cid, {}).get("explicit", ""), "typed_dimensions": ctx.get(cid, {}).get("typed", ""),
                             "period_start": ctx.get(cid, {}).get("period_start", ""), "period_end": ctx.get(cid, {}).get("period_end", ""),
                             "instant": ctx.get(cid, {}).get("instant", "")})
                for t in v.get("TradingSymbol", []):
                    facts.append({"accession": r.accession, "ticker": t, "context_id": cid,
                                  "trading_symbol": t, "security_12b_title": ";".join(v.get("Security12bTitle", [])),
                                  "security_12g_title": ";".join(v.get("Security12gTitle", [])),
                                  "exchange": ";".join(v.get("SecurityExchangeName", [])), "entity_cik": ctx.get(cid, {}).get("cik", ""),
                                  "explicit_dimensions": ctx.get(cid, {}).get("explicit", ""), "typed_dimensions": ctx.get(cid, {}).get("typed", ""),
                                  "document_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    out = pd.DataFrame(rows)
    out.to_csv(a.out / "p17_2_8_3_1_anchor_identity_results.csv", index=False)
    pd.DataFrame(facts).to_csv(a.out / "p17_2_8_3_1_raw_xbrl_facts.csv", index=False)
    pd.DataFrame(ctxs).drop_duplicates().to_csv(a.out / "p17_2_8_3_1_context_registry.csv", index=False)
    anchor = out.groupby(["anchor", "anchor_date"]).agg(
        total=("ticker", "size"), candidate_cik=("selected_cik", lambda x: sum(1 for v in x if pd.notna(v) and str(v) != "")),
        verified=("identity_status", lambda x: (x == "VERIFIED_RECONFIRMED").sum()),
        ambiguous=("identity_status", lambda x: (x == "AMBIGUOUS_SECURITY_CONTEXT").sum()),
        title_missing=("identity_status", lambda x: (x == "REVOKED_TITLE_MISSING").sum()),
        no_filing=("identity_status", lambda x: (x == "NO_HISTORICAL_FILING").sum()),
        unverified=("identity_status", lambda x: (x == "FILING_FOUND_IDENTITY_UNVERIFIED").sum())).reset_index()
    anchor.to_csv(a.out / "p17_2_8_3_1_anchor_summary.csv", index=False)
    exc = out[out.identity_status.isin(["FILING_FOUND_IDENTITY_UNVERIFIED", "AMBIGUOUS_SECURITY_CONTEXT", "REVOKED_TITLE_MISSING"])]
    exc.to_csv(a.out / "p17_2_8_3_1_exception_disposition.csv", index=False)
    # group reconciliation
    grp = out.groupby(["group", "identity_status"]).size().reset_index(name="rows")
    grp.to_csv(a.out / "p17_2_8_3_1_reconciliation.csv", index=False)
    # P390/P10 actual use
    p390 = pd.read_csv(P390, dtype=str)
    p390["cand"] = p390.candidate_cik.where(p390.candidate_cik.notna(), p390.cik).astype(str).str.zfill(10)
    p10 = pd.read_csv(P10, dtype=str)
    used390 = out[out.group == "NEW_38"]
    p10_hits = p10[p10.ticker.isin(out.ticker)]
    pd.DataFrame([{"source": "PR390", "rows": len(p390), "samples_new38": len(used390), "verified_new38": int((used390.identity_status == "VERIFIED_RECONFIRMED").sum())},
                  {"source": "P10", "rows": len(p10), "exact_ticker_hits": len(p10_hits), "verified_added": 0}]).to_csv(a.out / "p17_2_8_3_1_cik_conflicts.csv", index=False)
    # conflict actual: multiple selected ciks per key impossible; context mismatch
    mismatch = out[(out.context_entity_cik != "") & (out.context_entity_cik != out.selected_cik)]
    pd.DataFrame([{"checked_rows": len(out), "context_mismatches": len(mismatch), "rule": "selected_cik != context_entity_cik"}]).to_csv(a.out / "p17_2_8_3_1_cik_conflicts.csv", mode="a", header=False, index=False)
    pd.DataFrame([{"input_file_reads": 2, "raw_documents_attempted": len(docs), "raw_document_cache_reads": len(docs),
                   "cache_misses": len(out) - len(docs), "parse_success": parse_ok, "parse_exceptions": parse_err,
                   "network_requests": 0, "http_errors": 0}]).to_csv(a.out / "p17_2_8_3_1_request_audit.csv", index=False)
    summary = {"samples": len(out), "raw_documents": len(docs), "verified": int((out.identity_status == "VERIFIED_RECONFIRMED").sum()),
               "status": out.identity_status.value_counts().to_dict(), "anchor": anchor.to_dict("records"),
               "parse_success": parse_ok, "parse_errors": parse_err, "network_requests": 0,
               "business_sha256": hashlib.sha256((a.out / "p17_2_8_3_1_anchor_identity_results.csv").read_bytes()).hexdigest()}
    (a.out / "p17_2_8_3_1_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    files = {}
    for p in a.out.iterdir():
        if p.suffix in {".csv", ".json"} and p.name != "p17_2_8_3_1_output_manifest.json":
            files[p.name] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
    (a.out / "p17_2_8_3_1_output_manifest.json").write_text(json.dumps({"outputs": files, "business_sha256": summary["business_sha256"]}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
