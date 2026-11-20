#!/usr/bin/env python3
"""P17.2.1 filing metadata repair and local cover XBRL re-extraction."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pandas as pd
from lxml import html

OUT = Path("data/research/p17_2_1"); OUT.mkdir(parents=True, exist_ok=True)
FILINGS = Path("../_us_audit/repo_main/data/sec/filings_p43")
P13 = Path("../_us_p131/data/research/p13_1/p13_1_stock_coverage.csv")
P390 = Path("data/research/p17_2/p17_2_sample_universe.csv") if Path("data/research/p17_2/p17_2_sample_universe.csv").exists() else None


def cik10(v):
    s = re.sub(r"\.0$", "", str(v)).strip()
    return s.zfill(10) if s.isdigit() else ""


def metadata(d: Path):
    idx = next(iter(d.glob("*-index.html")), None)
    if not idx: return {}
    txt = idx.read_text(encoding="utf-8", errors="replace")
    form = re.search(r"<strong>Form\s+([^<]+)</strong>", txt)
    filed = re.search(r"Filing Date</div>\s*<div class=\"info\">([^<]+)", txt)
    accepted = re.search(r"Accepted</div>\s*<div class=\"info\">([^<]+)", txt)
    period = re.search(r"Period of Report</div>\s*<div class=\"info\">([^<]+)", txt)
    cik = re.search(r"CIK=(\d+)", txt)
    return {"form": form.group(1).strip() if form else "", "filing_date": filed.group(1).strip() if filed else "",
            "acceptance_datetime": accepted.group(1).strip() if accepted else "",
            "report_period": period.group(1).strip() if period else "",
            "registrant_cik": cik10(cik.group(1)) if cik else ""}


def parse_inline(path: Path):
    root = html.parse(str(path)).getroot()
    contexts = {}
    for c in root.xpath("//*[contains(local-name(),'context')]"):
        cid = c.get("id"); ident = c.xpath(".//*[contains(local-name(),'identifier')]/text()")
        dims = []
        for m in c.xpath(".//*[contains(local-name(),'explicitmember')]"):
            dims.append((m.get("dimension", ""), (m.text or "").strip()))
        contexts[cid] = {"cik": cik10(ident[0]) if ident else "", "dimensions": dims}
    facts = []
    for el in root.xpath("//*[contains(local-name(),'nonnumeric') or contains(local-name(),'nonNumeric')]"):
        name = el.get("name") or ""
        if name.lower().startswith("dei:"):
            facts.append({"tag": name, "value": re.sub(r"\s+", " ", el.text or "").strip(), "context": el.get("contextRef") or ""})
    return contexts, facts


rows = []; obs = []
for d in sorted(FILINGS.iterdir()):
    if not d.is_dir() or not (d / "index.json").exists(): continue
    meta = metadata(d)
    items = json.loads((d / "index.json").read_text(encoding="utf-8", errors="replace")).get("directory", {}).get("item", [])
    htm = [i for i in items if i["name"].lower().endswith((".htm", ".html")) and "index" not in i["name"].lower() and not i["name"].startswith("R")]
    if not htm: continue
    def size(i):
        try: return int(i.get("size") or 0)
        except Exception: return 0
    primary = max(htm, key=size)["name"]; doc = d / primary
    if not doc.exists(): continue
    ctx, facts = parse_inline(doc)
    file_cik = next((v["cik"] for v in ctx.values() if v["cik"]), "")
    acc = d.name
    acc_year = "20" + acc[10:12] if len(acc) >= 12 else ""
    rows.append({"accession": acc, "accession_year": acc_year, "source_dir": str(d), "primary_document": primary,
                 "document_sha256": hashlib.sha256(doc.read_bytes()).hexdigest(),
                 "form": meta.get("form", ""), "filing_date": meta.get("filing_date", ""), "acceptance_datetime": meta.get("acceptance_datetime", ""),
                 "report_period": meta.get("report_period", ""), "registrant_cik_index": meta.get("registrant_cik", ""),
                 "xbrl_context_cik": file_cik, "cik_match": bool(file_cik and file_cik == meta.get("registrant_cik", "")),
                 "symbol_facts": sum(1 for f in facts if f["tag"].lower() == "dei:tradingsymbol")})
    for f in facts:
        if f["tag"].lower() != "dei:tradingsymbol": continue
        c = ctx.get(f["context"], {"cik": "", "dimensions": []})
        title = next((x["value"] for x in facts if x["tag"].lower() == "dei:security12btitle" and x["context"] == f["context"]), "")
        exch = next((x["value"] for x in facts if x["tag"].lower() == "dei:securityexchangename" and x["context"] == f["context"]), "")
        obs.append({"ticker": f["value"], "security_title": title,
                    "security_class_axis": ";".join(a for a, b in c["dimensions"]),
                    "security_class_member": ";".join(b for a, b in c["dimensions"]), "exchange": exch,
                    "accession": acc, "form": meta.get("form", ""), "filing_date": meta.get("filing_date", ""),
                    "acceptance_datetime": meta.get("acceptance_datetime", ""), "report_period": meta.get("report_period", ""),
                    "issuer_cik": c["cik"], "registrant_cik": meta.get("registrant_cik", ""),
                    "identity_status": "VERIFIED_AT_FILING_ACCEPTANCE" if c["cik"] and c["cik"] == meta.get("registrant_cik", "") else "CANDIDATE_ONLY",
                    "document_sha256": rows[-1]["document_sha256"]})
reg = pd.DataFrame(rows); ob = pd.DataFrame(obs)
reg.to_csv(OUT / "p17_2_1_filing_registry.csv", index=False)
ob.to_csv(OUT / "p17_2_1_filing_identity_observations.csv", index=False)
reg["year"] = reg.accession_year
ob["year"] = "20" + ob.accession.astype(str).str[10:12]
summary = {"filings": len(reg), "forms": reg.form.value_counts().to_dict(),
           "accession_years": reg.accession_year.value_counts().sort_index().to_dict(),
           "historical_filings_2020_2024": int(reg.year.isin(["2020", "2021", "2022", "2023", "2024"]).sum()),
           "symbol_facts": len(ob), "historical_symbol_facts": int(ob.year.isin(["2020", "2021", "2022", "2023", "2024"]).sum()),
           "historical_tickers": sorted(ob[ob.year.isin(["2020", "2021", "2022", "2023", "2024"])].ticker.unique().tolist()),
           "cik_match_rate": float(reg.cik_match.mean()) if len(reg) else 0,
           "verified_facts": int((ob.identity_status == "VERIFIED_AT_FILING_ACCEPTANCE").sum()),
           "status": "IDENTITY_OBSERVATION_PARTIAL" if len(ob) else "DATA_BLOCKED"}
(OUT / "p17_2_1_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
files = {}
for p in OUT.iterdir():
    if p.suffix in {".csv", ".json"}:
        files[p.name] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
(OUT / "p17_2_1_manifest.json").write_text(json.dumps({"outputs": files,
    "inputs": {"filings_cache": str(FILINGS)}}, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
