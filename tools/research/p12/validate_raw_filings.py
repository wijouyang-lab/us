"""Validate 10 P12.3 issuers against their raw XBRL filing instance."""
from __future__ import annotations

import csv
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data/research/p12_3"
H = {"User-Agent": "P12 SEC PIT pilot contact@example.com"}
CHECK = {"Revenue", "NetIncome", "TotalAssets", "OperatingCashFlow", "TotalDebt", "SharesOutstanding"}
SELECT = ["AAPL", "MSFT", "JNJ", "WMT", "CAT", "XOM", "MON", "RTN", "BP", "SAP"]


def _local(tag: str) -> str:
    return tag.split("}")[-1]


def _parse_instance(path: Path):
    root = ET.parse(path).getroot()
    contexts = {}
    for c in root.iter():
        if _local(c.tag) != "context":
            continue
        cid = c.attrib.get("id")
        start = end = instant = None
        has_dim = False
        for x in c.iter():
            if _local(x.tag) == "startDate":
                start = (x.text or "").strip()
            elif _local(x.tag) == "endDate":
                end = (x.text or "").strip()
            elif _local(x.tag) == "instant":
                instant = (x.text or "").strip()
            elif _local(x.tag) == "explicitMember":
                has_dim = True
        contexts[cid] = {"start": start, "end": end or instant, "dim": has_dim}
    facts = []
    for el in root.iter():
        if "contextRef" not in el.attrib:
            continue
        ctx = contexts.get(el.attrib.get("contextRef"), {})
        if ctx.get("dim"):
            continue
        facts.append({"tag": _local(el.tag), "context": el.attrib.get("contextRef"), "start": ctx.get("start"), "end": ctx.get("end"), "unit": el.attrib.get("unitRef", ""), "value": (el.text or "").strip()})
    return facts


def main() -> int:
    panel = pd.read_csv(OUT / "p12_3_accession_fact_panel.csv", dtype={"cik": str})
    sample = pd.read_csv(ROOT / "data/research/p12_3_expanded_universe.csv", dtype={"cik": str})
    sample["cik"] = sample.cik.str.zfill(10)
    cache = ROOT / "cache_raw"; cache.mkdir(exist_ok=True)
    filing_rows, rec_rows = [], []
    for ticker in SELECT:
        s = sample[sample.ticker == ticker].iloc[0]
        cik = s.cik
        p = panel[(panel.cik.str.zfill(10) == cik) & panel.form.isin(["10-K", "20-F", "40-F"])].sort_values("filing_date")
        if p.empty:
            filing_rows.append({"ticker": ticker, "cik": cik, "status": "NO_10K_FACTS"})
            continue
        acc = p.iloc[-1].accession
        meta = p[p.accession == acc].iloc[-1]
        idx_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-','')}/index.json"
        r = requests.get(idx_url, headers=H, timeout=60)
        r.raise_for_status()
        names = [x["name"] for x in r.json()["directory"]["item"]]
        xmls = [n for n in names if n.endswith(".xml") and not re.search(r"(_cal|_def|_lab|_pre|FilingSummary)\.xml$", n)]
        if not xmls:
            filing_rows.append({"ticker": ticker, "cik": cik, "accession": acc, "status": "NO_XBRL_INSTANCE"})
            continue
        xml_name = sorted(xmls, key=lambda n: (not n.endswith("_htm.xml"), -len(n)))[0]
        raw_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-','')}/{xml_name}"
        rp = cache / f"{ticker}_{xml_name}"
        if not rp.exists():
            rp.write_bytes(requests.get(raw_url, headers=H, timeout=90).content)
        raw = _parse_instance(rp)
        filing_rows.append({"ticker": ticker, "cik": cik, "accession": acc, "form": meta.form, "filing_date": meta.filing_date, "acceptance_datetime": meta.acceptance_datetime, "period_end": meta.period_end, "raw_instance": raw_url, "raw_facts": len(raw), "status": "PARSED"})
        sub = p[p.accession == acc]
        for metric in CHECK:
            pr = sub[sub.metric == metric].dropna(subset=["value"]).copy()
            if metric in {"Revenue", "NetIncome", "OperatingCashFlow", "Capex"}:
                pr["dur"] = (pd.to_datetime(pr.period_end) - pd.to_datetime(pr.period_start)).dt.days
                pr = pr.sort_values(["dur", "period_end"])
            else:
                pr = pr.sort_values("period_end")
            if pr.empty:
                rec_rows.append({"ticker": ticker, "cik": cik, "accession": acc, "metric": metric, "status": "PANEL_MISSING"})
                continue
            prow = pr.iloc[-1]
            cand = [f for f in raw if f["tag"] == prow.tag and f["end"] == str(prow.period_end)]
            if metric in {"Revenue", "NetIncome", "OperatingCashFlow", "Capex"} and cand:
                cand = sorted(cand, key=lambda f: (pd.to_datetime(f["end"]) - pd.to_datetime(f["start"])).days if f.get("start") else -1, reverse=True)
            if not cand:
                rec_rows.append({"ticker": ticker, "cik": cik, "accession": acc, "metric": metric, "panel_value": prow.value, "raw_value": None, "status": "RAW_TAG_MISSING", "tag": prow.tag, "period_end": prow.period_end})
                continue
            rv = float(cand[0]["value"].replace(",", ""))
            pv = float(prow.value)
            if abs(pv - rv) <= max(1.0, abs(pv) * 1e-6):
                status = "MATCH"
            elif abs(pv - rv) <= max(1.0, abs(pv) * 0.01):
                status = "ROUNDING_OR_UNIT_SCALE"
            else:
                status = "CONFLICT"
            rec_rows.append({"ticker": ticker, "cik": cik, "accession": acc, "metric": metric, "panel_value": pv, "raw_value": rv, "status": status, "tag": prow.tag, "period_end": prow.period_end})
    pd.DataFrame(filing_rows).to_csv(OUT / "p12_3_filing_validation.csv", index=False)
    pd.DataFrame(rec_rows).to_csv(OUT / "p12_3_fact_reconciliation.csv", index=False)
    print({"filings": len(filing_rows), "checks": len(rec_rows), "status": pd.Series([r.get("status") for r in rec_rows]).value_counts().to_dict()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
