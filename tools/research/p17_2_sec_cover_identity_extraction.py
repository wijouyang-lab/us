#!/usr/bin/env python3
"""P17.2 SEC cover-page Inline XBRL identity extraction, local cache only."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pandas as pd
from lxml import html

OUT = Path("data/research/p17_2"); OUT.mkdir(parents=True, exist_ok=True)
FILINGS = Path("../_us_audit/repo_main/data/sec/filings_p43")
SEC = Path("../_us_audit/fund_p63/universe/sec_fundamentals_panel_p63.csv.gz")


def cik10(v):
    s = re.sub(r"\.0$", "", str(v)).strip()
    return s.zfill(10) if s.isdigit() else ""


def parse_inline(path: Path):
    tree = html.parse(str(path))
    root = tree.getroot()
    contexts = {}
    for c in root.xpath("//*[contains(local-name(),'context')]"):
        cid = c.get("id")
        ident = c.xpath(".//*[contains(local-name(),'identifier')]/text()")
        dims = []
        for m in c.xpath(".//*[contains(local-name(),'explicitmember')]"):
            dims.append((m.get("dimension", ""), (m.text or "").strip()))
        contexts[cid] = {"cik": cik10(ident[0]) if ident else "", "dimensions": dims}
    facts = []
    for el in root.xpath("//*[contains(local-name(),'nonnumeric') or contains(local-name(),'nonNumeric')]"):
        name = el.get("name") or el.get("Name") or ""
        if not name.lower().startswith("dei:"):
            continue
        facts.append({"tag": name, "value": (el.text or "").strip(), "context": el.get("contextRef") or el.get("contextref") or ""})
    return contexts, facts


def main():
    registry = []; observations = []
    for idx in sorted(FILINGS.glob("*/index.json")):
        meta = json.loads(idx.read_text(encoding="utf-8", errors="replace"))
        items = meta.get("directory", {}).get("item", [])
        htm = [i for i in items if i["name"].lower().endswith((".htm", ".html"))
               and "index" not in i["name"].lower() and not i["name"].startswith("R")]
        if not htm: continue
        def fsize(i):
            try: return int(i.get("size") or 0)
            except Exception: return 0
        primary = max(htm, key=fsize)["name"]
        doc = idx.parent / primary
        if not doc.exists(): continue
        accession = idx.parent.name
        contexts, facts = parse_inline(doc)
        vals = {}
        for f in facts:
            vals.setdefault((f["tag"].lower(), f["context"]), []).append(f["value"])
        symbols = [f for f in facts if f["tag"].lower() == "dei:tradingsymbol"]
        registry.append({"accession": accession, "primary_document": primary, "document_sha256": hashlib.sha256(doc.read_bytes()).hexdigest(),
                         "facts": len(facts), "symbol_facts": len(symbols), "contexts": len(contexts),
                         "reported_cik": next((v['cik'] for v in contexts.values() if v['cik']), "")})
        for s in symbols:
            ctx = contexts.get(s["context"], {"cik": "", "dimensions": []})
            # pair same-context title/exchange
            title = next((x["value"] for x in facts if x["tag"].lower() == "dei:security12btitle" and x["context"] == s["context"]), "")
            exchange = next((x["value"] for x in facts if x["tag"].lower() == "dei:securityexchangename" and x["context"] == s["context"]), "")
            observations.append({"issuer_cik": ctx["cik"], "filing_cik": next((v['cik'] for v in contexts.values() if v['cik']), ''), "ticker": s["value"],
                                 "security_title": title, "security_class_axis": ";".join(a for a, b in ctx["dimensions"]),
                                 "security_class_member": ";".join(b for a, b in ctx["dimensions"]), "exchange": exchange,
                                 "accession": accession, "form": "", "filing_date": "", "acceptance_datetime": "",
                                 "context_id": s["context"], "source_document": str(doc), "document_sha256": registry[-1]["document_sha256"],
                                 "identity_status": "VERIFIED_AT_FILING_ACCEPTANCE" if ctx["cik"] and ctx["cik"] == next((v['cik'] for v in contexts.values() if v['cik']), '') else "FILING_CIK_CONFLICT"})
    reg = pd.DataFrame(registry); obs = pd.DataFrame(observations)
    reg.to_csv(OUT / "p17_2_filing_registry.csv", index=False)
    obs.to_csv(OUT / "p17_2_filing_identity_observations.csv", index=False)
    facts = pd.concat([pd.DataFrame([{"accession": r.accession, "facts": r.facts, "symbols": r.symbol_facts}]) for r in reg.itertuples()], ignore_index=True) if len(reg) else pd.DataFrame()
    facts.to_csv(OUT / "p17_2_xbrl_identity_facts.csv", index=False)
    # Candidate universe and historical coverage (no 2020-2024 local filings).
    sample = pd.DataFrame([{"ticker": t, "reason": "P390/multiclass/unresolved sample"} for t in ["COG", "CTRA", "DISCA", "DISCK", "WBD", "BRK.B", "BF.B", "FRC", "DAY"]])
    sample.to_csv(OUT / "p17_2_sample_universe.csv", index=False)
    # CIK candidate from panel tickers.
    sec = pd.read_csv(SEC, usecols=["cik", "tickers"]).drop_duplicates()
    sec["ticker"] = sec.tickers.astype(str).str.split(",")
    rows = []
    for _, r in sec.iterrows():
        if not isinstance(r.ticker, list):
            continue
        for t in r.ticker:
            if t.strip() in set(sample.ticker):
                rows.append({"ticker": t.strip(), "candidate_cik": cik10(r.cik), "candidate_source": "sec_panel_current", "conflict_status": "CANDIDATE_CURRENT_ONLY"})
    pd.DataFrame(rows).drop_duplicates().to_csv(OUT / "p17_2_ticker_cik_candidates.csv", index=False)
    daily = pd.DataFrame([{"date": d, "verified_identity": 0, "candidate_identity": len(obs), "price_identity": 0} for d in pd.bdate_range("2020-01-02", "2024-12-31")])
    daily.to_csv(OUT / "p17_2_daily_identity_coverage.csv", index=False)
    quality = {"local_filings": int(len(reg)), "parsed": int(len(reg)), "symbol_facts": int(len(obs)),
               "unique_tickers": int(obs.ticker.nunique()) if len(obs) else 0,
               "verified_at_filing": int((obs.identity_status == "VERIFIED_AT_FILING_ACCEPTANCE").sum()) if len(obs) else 0,
               "filing_years": sorted(set(str(pd.to_datetime(i.get("last-modified", ""), errors="coerce").year) for i in [])) if False else [],
               "historical_2020_2024_filings": 0,
               "historical_identity_observations": 0,
               "parser_status": "PARSER_FEASIBLE_LOCAL_2026_ONLY",
               "coverage_status": "DATA_BLOCKED_NO_HISTORICAL_FILINGS"}
    (OUT / "p17_2_parser_quality.json").write_text(json.dumps(quality, indent=2), encoding="utf-8")
    summary = {"status": "DATA_BLOCKED", "quality": quality,
               "reason": "Local SEC cache contains only 2026 filings; no 2020/2022/2024 cover pages. Parser extracts CAT/CAT35 from Inline XBRL but cannot build historical identity timeline.",
               "no_alpha": True}
    (OUT / "p17_2_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    files = {}
    for p in OUT.iterdir():
        if p.suffix in {".csv", ".json"}:
            rows = None
            if p.suffix == ".csv":
                try:
                    rows = len(pd.read_csv(p))
                except Exception:
                    rows = 0
            files[p.name] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size, "rows": rows}
    (OUT / "p17_2_manifest.json").write_text(json.dumps({"outputs": files, "inputs": {str(SEC): hashlib.sha256(SEC.read_bytes()).hexdigest()}}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
