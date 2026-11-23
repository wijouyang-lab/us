#!/usr/bin/env python3
"""P17.2.8.3.2 independent audit of 300 PIT identity samples from raw cache."""
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
BASE = Path("../_us_p17283/data/research/p17_2_8_3_1")


def cik10(v):
    s = re.sub(r"\.0$", "", str(v)).strip()
    return s.zfill(10) if s.isdigit() else ""


def parse(path):
    root = html.parse(str(path)).getroot()
    ctx = {}
    for c in root.xpath("//*[contains(local-name(),'context')]"):
        ident = c.xpath(".//*[contains(local-name(),'identifier')]/text()")
        exp = [f"{m.get('dimension','')}={m.text or ''}" for m in c.xpath(".//*[contains(local-name(),'explicitmember')]")]
        typ = [f"{m.get('dimension','')}=TYPED:{''.join(m.itertext())}" for m in c.xpath(".//*[contains(local-name(),'typedmember')]")]
        ps = c.xpath(".//*[contains(local-name(),'startdate')]/text()")
        pe = c.xpath(".//*[contains(local-name(),'enddate')]/text()")
        ctx[c.get('id')] = {"cik": cik10(ident[0]) if ident else "", "explicit": ";".join(exp), "typed": ";".join(typ),
                            "start": ps[0] if ps else "", "end": pe[0] if pe else ""}
    by = {}
    for el in root.xpath("//*[contains(local-name(),'nonnumeric')]"):
        local = (el.get('name') or '').split(':')[-1]
        if local in {"TradingSymbol", "Security12bTitle", "Security12gTitle", "SecurityExchangeName"}:
            by.setdefault(el.get("contextRef") or el.get("contextref") or "", {}).setdefault(local, []).append(re.sub(r"\s+", " ", el.text or "").strip())
    return ctx, by


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists() and any(a.out.iterdir()):
        raise SystemExit("REFUSING_NONEMPTY_OUTPUT")
    a.out.mkdir(parents=True, exist_ok=True)
    rows = pd.read_csv(BASE / "p17_2_8_3_1_anchor_identity_results.csv", dtype=str)
    docs = []; out = []; facts = []
    for _, r in rows.iterrows():
        cik = cik10(r.selected_cik) if pd.notna(r.selected_cik) else ""
        acc = str(r.accession) if pd.notna(r.accession) else ""
        primary = str(r.primary) if pd.notna(r.primary) else ""
        doc = None
        if acc and primary and cik:
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{primary}"
            for d in [P27 / "cache", P281 / "cache"]:
                p = d / hashlib.sha256(url.encode()).hexdigest()
                if p.exists(): doc = p; break
        status = "NO_HISTORICAL_CIK_CANDIDATE" if not cik else "NO_HISTORICAL_FILING"
        title = ""; ctxid = ""; ccik = ""; age = None; sha = ""; symbols = ""
        if acc and not doc and cik:
            status = "SUBMISSION_FOUND_DOCUMENT_MISSING"
        if doc:
            sha = hashlib.sha256(doc.read_bytes()).hexdigest()
            docs.append({"anchor": r.anchor, "ticker": r.ticker, "accession": acc, "path": str(doc), "sha256": sha})
            try:
                ctx, by = parse(doc)
                hits = [(cid, v) for cid, v in by.items() if r.ticker in v.get("TradingSymbol", [])]
                symbols = ";".join(sorted({t for v in by.values() for t in v.get("TradingSymbol", [])}))
                if not hits:
                    status = "FILING_FOUND_IDENTITY_UNVERIFIED"
                else:
                    titles = set(); empty = False
                    for cid, v in hits:
                        tt = [x for x in (v.get("Security12bTitle", []) + v.get("Security12gTitle", [])) if x]
                        if not tt: empty = True
                        titles.update(tt)
                    if empty and titles:
                        status = "AMBIGUOUS_SECURITY_CONTEXT"
                    elif not titles:
                        status = "SECURITY_TITLE_MISSING"
                    elif len(titles) > 1:
                        status = "AMBIGUOUS_SECURITY_CONTEXT"
                    else:
                        title = titles.pop(); ctxid = hits[0][0]; ccik = ctx.get(ctxid, {}).get("cik", "")
                        acceptance = pd.to_datetime(r.acceptance_utc, errors="coerce", utc=True)
                        cutoff = pd.Timestamp(r.anchor_date).tz_localize(ET).replace(hour=16).tz_convert("UTC")
                        age = (cutoff - acceptance).days if pd.notna(acceptance) else None
                        if ccik != cik: status = "CIK_MISMATCH"
                        elif pd.isna(acceptance): status = "ACCEPTANCE_UNVERIFIED"
                        elif acceptance > cutoff: status = "ACCEPTANCE_AFTER_CUTOFF"
                        elif age > 400: status = "STALE_PRIOR_POINT"
                        else: status = "VERIFIED_RECONFIRMED"
                for cid, v in by.items():
                    for t in v.get("TradingSymbol", []):
                        facts.append({"anchor": r.anchor, "ticker": t, "accession": acc, "context_id": cid,
                                      "trading_symbol": t, "security_12b_title": ";".join(v.get("Security12bTitle", [])),
                                      "security_12g_title": ";".join(v.get("Security12gTitle", [])),
                                      "exchange": ";".join(v.get("SecurityExchangeName", [])),
                                      "entity_cik": ctx.get(cid, {}).get("cik", ""),
                                      "explicit_dimensions": ctx.get(cid, {}).get("explicit", ""),
                                      "typed_dimensions": ctx.get(cid, {}).get("typed", ""),
                                      "period_start": ctx.get(cid, {}).get("start", ""), "period_end": ctx.get(cid, {}).get("end", ""),
                                      "document_sha256": sha})
            except Exception:
                status = "PARSE_ERROR"
        out.append({**r.to_dict(), "independent_status": status, "independent_title": title,
                    "contextRef": ctxid, "context_entity_cik": ccik, "evidence_age_days": age,
                    "document_sha256": sha, "all_trading_symbols": symbols})
    o = pd.DataFrame(out)
    o.to_csv(a.out / "row_level_reconciliation.csv", index=False)
    pd.DataFrame(docs).drop_duplicates().to_csv(a.out / "document_registry.csv", index=False)
    pd.DataFrame(facts).to_csv(a.out / "independent_raw_facts.csv", index=False)
    exc = o[~o.independent_status.isin(["VERIFIED_RECONFIRMED"])]
    exc.to_csv(a.out / "identity_exception_audit.csv", index=False)
    anchor = o.groupby(["anchor", "anchor_date"]).agg(total=("ticker", "size"),
        verified=("independent_status", lambda x: (x == "VERIFIED_RECONFIRMED").sum())).reset_index()
    anchor.to_csv(a.out / "anchor_coverage_recalculated.csv", index=False)
    # Recovery: no alternate cached accession registry exists beyond selected docs.
    rec = pd.DataFrame([{"status": "NO_ADDITIONAL_CACHED_ACCESSION_REGISTRY", "recovered": 0,
                         "note": "cache contains selected primary documents + submissions only"}])
    rec.to_csv(a.out / "cached_filing_recovery.csv", index=False)
    summary = {"samples": len(o), "raw_documents": len(docs), "verified": int((o.independent_status == "VERIFIED_RECONFIRMED").sum()),
               "status": o.independent_status.value_counts().to_dict(), "anchor": anchor.to_dict("records"),
               "network_requests": 0, "recovered": 0,
               "business_sha256": hashlib.sha256((a.out / "row_level_reconciliation.csv").read_bytes()).hexdigest()}
    (a.out / "independent_verification_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    inputs = {}
    for name, p in {"p283_results": BASE / "p17_2_8_3_1_anchor_identity_results.csv", "p27_cache": P27 / "cache", "p281_cache": P281 / "cache"}.items():
        inputs[name] = {"path": str(p), "exists": p.exists(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None}
    (a.out / "input_manifest.json").write_text(json.dumps(inputs, indent=2), encoding="utf-8")
    files = {}
    for p in a.out.iterdir():
        if p.suffix in {".csv", ".json"} and p.name != "output_manifest.json":
            files[p.name] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
    (a.out / "output_manifest.json").write_text(json.dumps({"outputs": files, "business_sha256": summary["business_sha256"]}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
