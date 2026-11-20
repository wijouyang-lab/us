#!/usr/bin/env python3
"""P17.2.5 XBRL context-level ticker/security reconciliation for 8 filings."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pandas as pd
from lxml import html

OUT = Path("data/research/p17_2_5"); OUT.mkdir(parents=True, exist_ok=True)
FILINGS = Path("../_us_audit/repo_main/data/sec/filings_p43")
P3 = Path("../_us_p1723/data/research/p17_2_3")
h = pd.read_csv(P3 / "p17_2_3_submission_header_metadata.csv", dtype=str)
pilot = pd.read_csv(P3 / "p17_2_3_pilot_manifest.csv", dtype=str)


def cik10(v):
    s = re.sub(r"\.0$", "", str(v)).strip()
    return s.zfill(10) if s.isdigit() else ""


def parse(path: Path):
    root = html.parse(str(path)).getroot()
    ctx = {}
    for c in root.xpath("//*[contains(local-name(),'context')]"):
        cid = c.get("id"); ident = c.xpath(".//*[contains(local-name(),'identifier')]/text()")
        dims = []
        for m in c.xpath(".//*[contains(local-name(),'explicitmember')]"):
            dims.append((m.get("dimension", ""), (m.text or "").strip()))
        ctx[cid] = {"cik": cik10(ident[0]) if ident else "", "dims": dims}
    facts = []
    for el in root.xpath("//*[contains(local-name(),'nonnumeric')]"):
        name = el.get("name") or ""
        if name.lower().startswith("dei:"):
            facts.append({"tag": name.split(":")[-1], "value": re.sub(r"\s+", " ", el.text or "").strip(),
                          "context": el.get("contextRef") or el.get("contextref") or "", "id": el.get("id") or ""})
    return ctx, facts


facts_rows = []; ctx_rows = []; mapping = []; issuer_rows = []
for _, p in pilot.iterrows():
    acc = p.accession; doc = FILINGS / acc / p.primary
    if not doc.exists():
        continue
    ctx, facts = parse(doc)
    digest = hashlib.sha256(doc.read_bytes()).hexdigest()
    for cid, c in ctx.items():
        ctx_rows.append({"accession": acc, "context_id": cid, "entity_cik": c["cik"],
                         "dimensions": ";".join(f"{a}={b}" for a, b in c["dims"]),
                         "axes": ";".join(a for a, b in c["dims"]), "members": ";".join(b for a, b in c["dims"])})
    for f in facts:
        facts_rows.append({"accession": acc, "tag": f["tag"], "value": f["value"], "context_id": f["context"],
                           "fact_id": f["id"], "document": p.primary, "document_sha256": digest})
    byctx = {}
    for f in facts:
        byctx.setdefault(f["context"], {}).setdefault(f["tag"], []).append(f["value"])
    for cid, vals in byctx.items():
        tickers = vals.get("TradingSymbol", [])
        if not tickers:
            continue
        c = ctx.get(cid, {"cik": "", "dims": []})
        titles = vals.get("Security12bTitle", []); ex = vals.get("SecurityExchangeName", [])
        for t in tickers:
            title = titles[0] if titles else ""
            exchange = ex[0] if ex else ""
            dims = ";".join(f"{a}={b}" for a, b in c["dims"])
            is_issuer = bool(c["cik"] and c["cik"] in str(p.filers))
            status = "VERIFIED_SECURITY_TICKER_POINT" if (title and c["cik"] and is_issuer) else "SECURITY_UNRESOLVED"
            mapping.append({"ticker": t, "issuer_cik": c["cik"], "filing_cik": p.filers,
                            "accession": acc, "security_title": title, "exchange": exchange,
                            "context_id": cid, "context_dimensions": dims,
                            "form": p.form, "filed_date": p.filed_date, "acceptance_raw": p.acceptance_raw,
                            "identity_status": status, "document": p.primary, "document_sha256": digest})
    issuer_rows.append({"accession": acc, "prefix_cik": acc[:10], "header_filers": p.filers,
                        "xbrl_context_ciks": ";".join(sorted({v["cik"] for v in ctx.values() if v["cik"]})),
                        "form": p.form, "filed_date": p.filed_date, "acceptance_raw": p.acceptance_raw})
pd.DataFrame(facts_rows).to_csv(OUT / "p17_2_5_raw_xbrl_facts.csv", index=False)
pd.DataFrame(ctx_rows).to_csv(OUT / "p17_2_5_context_registry.csv", index=False)
m = pd.DataFrame(mapping)
m.to_csv(OUT / "p17_2_5_fact_context_join.csv", index=False)
m.to_csv(OUT / "p17_2_5_ticker_security_mapping.csv", index=False)
pd.DataFrame(issuer_rows).to_csv(OUT / "p17_2_5_issuer_cik_reconciliation.csv", index=False)
m[m.ticker.isin(["GOOG", "GOOGL"])].to_csv(OUT / "p17_2_5_alphabet_class_audit.csv", index=False)
m[m.ticker.str.startswith("NEE.PR")].to_csv(OUT / "p17_2_5_nee_preferred_audit.csv", index=False)
m[m.identity_status == "VERIFIED_SECURITY_TICKER_POINT"].to_csv(OUT / "p17_2_5_verified_security_points.csv", index=False)
m[m.identity_status != "VERIFIED_SECURITY_TICKER_POINT"].to_csv(OUT / "p17_2_5_unresolved_candidates.csv", index=False)
pd.DataFrame([{"status": "NONE", "reason": "no explicit validity interval evidence"}]).to_csv(OUT / "p17_2_5_security_conflicts.csv", index=False)
summary = {"filings": len(pilot), "contexts": len(ctx_rows), "dei_facts": len(facts_rows), "symbol_points": len(m),
           "verified_security_points": int((m.identity_status == "VERIFIED_SECURITY_TICKER_POINT").sum()),
           "unresolved": int((m.identity_status != "VERIFIED_SECURITY_TICKER_POINT").sum()),
           "unique_verified_tickers": int(m[m.identity_status == "VERIFIED_SECURITY_TICKER_POINT"].ticker.nunique()),
           "verified_intervals": 0,
           "goog": m[m.ticker == "GOOG"][["ticker", "security_title", "identity_status"]].to_dict("records"),
           "googl": m[m.ticker == "GOOGL"][["ticker", "security_title", "identity_status"]].to_dict("records"),
           "status": "VERIFIED_CONTEXT_MAPPING" if (m.identity_status == "VERIFIED_SECURITY_TICKER_POINT").all() and len(m) == 16 else "PARTIAL"}
(OUT / "p17_2_5_coverage_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(OUT / "p17_2_5_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
files = {}
for p in OUT.iterdir():
    if p.suffix in {".csv", ".json"}:
        files[p.name] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
(OUT / "p17_2_5_manifest.json").write_text(json.dumps({"outputs": files}, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
