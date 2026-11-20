#!/usr/bin/env python3
"""P17.2.3 8-accession SEC historical metadata pilot. Cached, <=1 req/s."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

import pandas as pd
import requests

OUT = Path("data/research/p17_2_3"); CACHE = OUT / "cache"; OUT.mkdir(parents=True, exist_ok=True); CACHE.mkdir(parents=True, exist_ok=True)
UA = os.environ.get("SEC_USER_AGENT", "").strip()
if not UA:
    raise SystemExit("SEC_DOWNLOAD_BLOCKED_MISSING_USER_AGENT")
HEAD = {"User-Agent": UA}
REG = Path("../_us_p1721/data/research/p17_2_1/p17_2_1_filing_registry.csv")
OBS = Path("../_us_p1721/data/research/p17_2_1/p17_2_1_filing_identity_observations.csv")
audit = []


def get(url: str):
    p = CACHE / hashlib.sha256(url.encode()).hexdigest()
    if p.exists():
        audit.append({"url": url, "status": "CACHE", "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
        return p.read_bytes()
    for attempt in range(2):
        r = requests.get(url, headers=HEAD, timeout=40)
        if r.status_code == 200:
            p.write_bytes(r.content)
            audit.append({"url": url, "status": 200, "bytes": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()})
            time.sleep(1.0)
            return r.content
        if r.status_code in (403, 429):
            audit.append({"url": url, "status": r.status_code, "bytes": len(r.content), "sha256": ""})
            raise RuntimeError(f"HTTP {r.status_code}")
        time.sleep(2)
    raise RuntimeError("SEC_FAILED")


def parse_header(txt: bytes):
    s = txt.decode("utf-8", errors="replace")[:250000]
    def one(label):
        m = re.search(rf"{re.escape(label)}:\s*([^\r\n]+)", s)
        return m.group(1).strip() if m else ""
    acc = re.search(r"<ACCEPTANCE-DATETIME>\s*(\d+)", s)
    ciks = [x.zfill(10) for x in re.findall(r"CENTRAL INDEX KEY:\s*(\d+)", s)]
    name = re.search(r"COMPANY CONFORMED NAME:\s*([^\r\n]+)", s)
    return {"form": one("CONFORMED SUBMISSION TYPE"), "filed_date": one("FILED AS OF DATE"),
            "acceptance_raw": acc.group(1) if acc else "", "report_period": one("CONFORMED PERIOD OF REPORT"),
            "filers": ciks[:3], "company": name.group(1).strip() if name else ""}


reg = pd.read_csv(REG, dtype={"accession": str})
reg["acc"] = reg.accession.astype(str).str.replace(r"\D", "", regex=True)
hist = reg[reg.acc.str[10:12].isin(["20", "21", "22", "23", "24"])].copy()
obs = pd.read_csv(OBS, dtype={"accession": str})
rows = []; hdr_rows = []; master_rows = []; obs_rows = []
master_cache = {}
for _, r in hist.iterrows():
    acc = r.acc
    cik = acc[:10]
    url_dir = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/index.json"
    index_ok = False; primary = ""; index_cik = ""
    try:
        j = json.loads(get(url_dir).decode()); index_ok = True
        items = j.get("directory", {}).get("item", [])
        docs = [i for i in items if i["name"].lower().endswith((".htm", ".html")) and "index" not in i["name"].lower() and not i["name"].startswith("R")]
        docs.sort(key=lambda x: int(x.get("size") or 0), reverse=True)
        primary = docs[0]["name"] if docs else ""
    except Exception:
        pass
    txt_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{cik}-{acc[10:12]}-{acc[12:]}.txt"
    hdr = {}
    try:
        hdr = parse_header(get(txt_url))
    except Exception as e:
        hdr = {"error": str(e)}
    rows.append({"accession": acc, "index_ok": index_ok, "primary": primary, "form": hdr.get("form", ""), "filed_date": hdr.get("filed_date", ""),
                 "acceptance_raw": hdr.get("acceptance_raw", ""), "report_period": hdr.get("report_period", ""), "filers": ";".join(hdr.get("filers", []))})
    hdr_rows.append({"accession": acc, **hdr})
    # master index exact match by filed date quarter
    fd = hdr.get("filed_date", "")
    if len(fd) == 8:
        y, q = fd[:4], (int(fd[4:6]) - 1) // 3 + 1
        mu = f"https://www.sec.gov/Archives/edgar/full-index/{y}/QTR{q}/master.idx"
        try:
            if mu not in master_cache:
                master_cache[mu] = get(mu).decode("utf-8", errors="replace")
            dashed = f"{acc[:10]}-{acc[10:12]}-{acc[12:]}"
            line = next((ln for ln in master_cache[mu].splitlines() if dashed in ln or acc in ln), "")
            master_rows.append({"accession": acc, "master_url": mu, "master_line": line, "matched": bool(line)})
        except Exception as e:
            master_rows.append({"accession": acc, "master_url": mu, "master_line": "", "matched": False, "error": str(e)})
    else:
        master_rows.append({"accession": acc, "master_url": "", "master_line": "", "matched": False, "error": "NO_FILED_DATE"})
    for _, o in obs[obs.accession.astype(str).str.replace(r"\D", "", regex=True) == acc].iterrows():
        cik_ok = bool(hdr.get("filers") and (acc[:10] in hdr["filers"]))
        obs_rows.append({"ticker": o.ticker, "accession": acc, "form": hdr.get("form", ""), "filed_date": hdr.get("filed_date", ""),
                         "acceptance_raw": hdr.get("acceptance_raw", ""), "report_period": hdr.get("report_period", ""),
                         "filer_ciks": ";".join(hdr.get("filers", [])), "cik_ok": cik_ok,
                         "identity_status": "VERIFIED_AT_FILING_ACCEPTANCE" if cik_ok and hdr.get("acceptance_raw") else "CANDIDATE_ONLY"})
reg_out = pd.DataFrame(rows); hdr_out = pd.DataFrame(hdr_rows); master = pd.DataFrame(master_rows); obs_out = pd.DataFrame(obs_rows)
reg_out.to_csv(OUT / "p17_2_3_pilot_manifest.csv", index=False)
hdr_out.to_csv(OUT / "p17_2_3_submission_header_metadata.csv", index=False)
master.to_csv(OUT / "p17_2_3_master_index_metadata.csv", index=False)
obs_out.to_csv(OUT / "p17_2_3_filing_identity_observations.csv", index=False)
pd.DataFrame(audit).to_csv(OUT / "p17_2_3_request_audit.csv", index=False)
pd.DataFrame([{"source": "filing_index", "status": "PILOT", "rows": len(reg_out)}]).to_csv(OUT / "p17_2_3_sec_index_metadata.csv", index=False)
summary = {"accessions": len(reg_out), "index_ok": int(reg_out.index_ok.sum()), "submission_header": int(reg_out.acceptance_raw.astype(bool).sum()),
           "filed_date": int(reg_out.filed_date.astype(bool).sum()), "acceptance": int(reg_out.acceptance_raw.astype(bool).sum()),
           "master_matched": int(master.matched.sum()), "symbol_facts": len(obs_out),
           "verified_facts": int((obs_out.identity_status == "VERIFIED_AT_FILING_ACCEPTANCE").sum()),
           "requests": len(audit), "status": "PILOT_PARTIAL"}
(OUT / "p17_2_3_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
