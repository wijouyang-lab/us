#!/usr/bin/env python3
"""P17.2.2 accession metadata recovery audit. No SEC requests without User-Agent."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import pandas as pd

OUT = Path("data/research/p17_2_2"); OUT.mkdir(parents=True, exist_ok=True)
REG = Path("../_us_p1721/data/research/p17_2_1/p17_2_1_filing_registry.csv")
OBS = Path("../_us_p1721/data/research/p17_2_1/p17_2_1_filing_identity_observations.csv")
P13 = Path("../_us_p131/data/research/p13_1/p13_1_stock_coverage.csv")
UA = os.environ.get("SEC_USER_AGENT", "").strip()
UA_PRESENT = bool(UA)
# Never print the value.
UA_STATUS = "PRESENT" if UA_PRESENT else "MISSING"


def parse_accession(a: str):
    s = re.sub(r"\D", "", str(a))
    if len(s) != 18:
        return None
    return {"accession_no_dash": s, "accession_dashed": f"{s[:10]}-{s[10:12]}-{s[12:]}",
            "accession_prefix_cik": s[:10], "accession_year": "20" + s[10:12],
            "accession_sequence": s[12:],
            "archives_url": f"https://www.sec.gov/Archives/edgar/data/{int(s[:10])}/{s}/"}


reg = pd.read_csv(REG, dtype={"accession": str})
reg["accession_no_dash"] = reg.accession.astype(str).str.replace(r"\D", "", regex=True)
rows = []
for _, r in reg.iterrows():
    p = parse_accession(r.accession_no_dash)
    if not p:
        rows.append({"accession": r.accession, "parse_status": "INVALID_ACCESSION"}); continue
    rows.append({"accession": r.accession, **p, "parse_status": "PARSED",
                 "accession_year_from_digits": p["accession_year"]})
acc = pd.DataFrame(rows)
acc.to_csv(OUT / "p17_2_2_accession_registry.csv", index=False)
# Local metadata already recovered (only 2/75 in P17.2.1).
acc["has_local_form"] = reg.form.notna().values
acc["has_local_filed_date"] = reg.filing_date.notna().values
acc["has_local_acceptance"] = reg.acceptance_datetime.notna().values
acc["has_local_registrant_cik"] = reg.registrant_cik_index.notna().values
meta = {"accessions": len(acc), "parsed": int((acc.parse_status == "PARSED").sum()),
        "has_form": int(acc.has_local_form.sum()), "has_filed_date": int(acc.has_local_filed_date.sum()),
        "has_acceptance": int(acc.has_local_acceptance.sum()),
        "has_registrant_cik": int(acc.has_local_registrant_cik.sum()),
        "historical_2020_2024": int(acc.accession_year.isin(["2020", "2021", "2022", "2023", "2024"]).sum()),
        "metadata_complete": int((acc.has_local_form & acc.has_local_filed_date & acc.has_local_acceptance).sum())}
pd.DataFrame([meta]).to_csv(OUT / "p17_2_2_sec_index_metadata.csv", index=False)
pd.DataFrame([{"source": "local_index_html", "status": "NOT_QUERIED_SEC", "reason": "SEC_USER_AGENT missing"}]).to_csv(OUT / "p17_2_2_submission_header_metadata.csv", index=False)
pd.DataFrame([{"source": "master_index", "status": "NOT_QUERIED_SEC", "reason": "SEC_USER_AGENT missing"}]).to_csv(OUT / "p17_2_2_master_index_metadata.csv", index=False)
pd.DataFrame([{"source": "filing_index", "status": "NOT_QUERIED_SEC", "reason": "SEC_USER_AGENT missing"}]).to_csv(OUT / "p17_2_2_filing_download_audit.csv", index=False)
pd.DataFrame([{"source": "cik_cross_validation", "status": "BLOCKED", "reason": "no independent SEC index/header"}]).to_csv(OUT / "p17_2_2_cik_cross_validation.csv", index=False)
pd.DataFrame([{"source": "conflicts", "status": "NOT_COMPUTED"}]).to_csv(OUT / "p17_2_2_metadata_conflicts.csv", index=False)
pd.DataFrame([{"source": "acceptance", "status": "UNAVAILABLE"}]).to_csv(OUT / "p17_2_2_acceptance_timeline.csv", index=False)
# Observations.
obs = pd.read_csv(OBS, dtype={"accession": str})
obs["accession_no_dash"] = obs.accession.astype(str).str.replace(r"\D", "", regex=True)
obs["identity_status"] = "CANDIDATE_ONLY"
obs["metadata_verified"] = False
obs.to_csv(OUT / "p17_2_2_filing_identity_observations.csv", index=False)
hist = obs[obs.accession_no_dash.str[10:12].isin(["20", "21", "22", "23", "24"])]
# P13 membership overlap.
p13 = pd.read_csv(P13)
tickers = set(hist.ticker.astype(str))
p13set = set(p13.ticker.astype(str))
overlap = sorted(tickers & p13set)
coverage = {"historical_symbol_facts": len(hist), "historical_tickers": len(tickers),
            "p13_overlap_tickers": len(overlap), "p13_overlap_tickers_list": overlap,
            "historical_verified_facts": 0, "historical_point_observations": 0,
            "historical_verified_intervals": 0,
            "metadata_verified_filings": int(meta["metadata_complete"]),
            "status": "DATA_BLOCKED"}
pd.DataFrame([coverage]).to_csv(OUT / "p17_2_2_historical_identity_coverage.csv", index=False)
summary = {"user_agent_status": UA_STATUS, "download_status": "SEC_DOWNLOAD_BLOCKED_MISSING_USER_AGENT" if not UA_PRESENT else "READY_NOT_RUN",
           "metadata": meta, "coverage": coverage,
           "overall": "DATA_BLOCKED",
           "reason": "No SEC_USER_AGENT configured; no SEC requests were made. Local metadata exists for only 2/75 accessions."}
(OUT / "p17_2_2_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
files = {}
for p in OUT.iterdir():
    if p.suffix in {".csv", ".json"}:
        files[p.name] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
(OUT / "p17_2_2_manifest.json").write_text(json.dumps({"outputs": files, "note": "No SEC requests; UA missing"}, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
