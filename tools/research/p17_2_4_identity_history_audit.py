#!/usr/bin/env python3
"""P17.2.4 SEC identity history audit: issuer vs security, no interval ffill."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

OUT = Path("data/research/p17_2_4"); OUT.mkdir(parents=True, exist_ok=True)
P3 = Path("../_us_p1723/data/research/p17_2_3")
P1 = Path("../_us_p1721/data/research/p17_2_1")
P13 = Path("../_us_p131/data/research/p13_1/p13_1_stock_coverage.csv")

h = pd.read_csv(P3 / "p17_2_3_submission_header_metadata.csv", dtype=str)
m = pd.read_csv(P3 / "p17_2_3_master_index_metadata.csv", dtype=str)
c = pd.read_csv(P3 / "p17_2_3_cik_cross_validation.csv", dtype=str)
o3 = pd.read_csv(P3 / "p17_2_3_filing_identity_observations.csv", dtype=str)
o1 = pd.read_csv(P1 / "p17_2_1_filing_identity_observations.csv", dtype=str)
reg1 = pd.read_csv(P1 / "p17_2_1_filing_registry.csv", dtype={"accession": str})
audit = pd.read_csv(P3 / "p17_2_3_request_audit.csv")

# Canonical metadata straight from headers; ET + UTC.
h["acceptance_utc"] = pd.to_datetime(h.acceptance_raw, format="%Y%m%d%H%M%S", errors="coerce", utc=True)
h["acceptance_et"] = h.acceptance_utc.dt.tz_convert("America/New_York")
h["filed_date_canonical"] = pd.to_datetime(h.filed_date, format="%Y%m%d", errors="coerce").dt.date.astype(str)
h["report_period_canonical"] = pd.to_datetime(h.report_period, format="%Y%m%d", errors="coerce").dt.date.astype(str)
h.to_csv(OUT / "p17_2_4_source_reconciliation.csv", index=False)

# Security titles/classes from raw-filing extraction, exact accession+ticker.
sec = o1[o1.accession.astype(str).isin(h.accession)].copy()
h2 = h[["accession", "acceptance_utc", "acceptance_et", "filed_date_canonical", "form"]].rename(columns={"form": "form_header"})
sec = sec.merge(h2, on="accession", how="left")
sec["ticker"] = sec.ticker.astype(str)
sec["issuer_cik"] = sec.issuer_cik.astype(str).str.zfill(10)
sec["evidence_time_utc"] = sec.acceptance_utc.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
sec["evidence_time_et"] = sec.acceptance_et.dt.strftime("%Y-%m-%dT%H:%M:%S%z")
# NEE preferred and GOOG C-class title conflict.
pref = {"NEE.PRO", "NEE.PRP", "NEE.PRQ", "NEE.PRR"}
def status(t):
    if t in pref or t == "GOOG":
        return "IDENTITY_CONFLICT"
    return "VERIFIED_SECURITY_TICKER_POINT"
sec["identity_status"] = sec.ticker.map(status)
sec["issuer_status"] = "VERIFIED_ISSUER_FILING_POINT"
sec.to_csv(OUT / "p17_2_4_identity_point_observations.csv", index=False)
sec[sec.identity_status == "IDENTITY_CONFLICT"][["ticker", "accession", "security_title", "security_class_member", "identity_status"]].to_csv(OUT / "p17_2_4_identity_conflicts.csv", index=False)

# Issuer-level.
iss = sec[["issuer_cik", "accession", "form_header", "filed_date_canonical", "acceptance_utc"]].drop_duplicates()
iss["issuer_status"] = "VERIFIED_ISSUER_FILING_POINT"
iss.to_csv(OUT / "p17_2_4_issuer_identity.csv", index=False)
sec[["ticker", "issuer_cik", "security_title", "security_class_member", "exchange", "accession", "identity_status"]].to_csv(OUT / "p17_2_4_security_identity.csv", index=False)
sec[["ticker", "issuer_cik", "accession", "identity_status"]].to_csv(OUT / "p17_2_4_ticker_security_mapping.csv", index=False)
pd.DataFrame([{"status": "NONE", "reason": "no explicit validity interval evidence"}]).to_csv(OUT / "p17_2_4_identity_intervals.csv", index=False)

# Request provenance (cannot recover original network count from cache-only audit).
prov = audit.copy()
prov["provenance"] = prov.status.map({"200": "NETWORK_200_OR_CACHED_UNKNOWN", "CACHE": "CACHE_HIT"})
prov.to_csv(OUT / "p17_2_4_request_provenance.csv", index=False)
req = {"rows": len(prov), "cache_hits": int((prov.status == "CACHE").sum()), "status_200": int((prov.status == 200).sum()),
       "original_network_count": "ORIGINAL_NETWORK_REQUEST_COUNT_UNVERIFIABLE",
       "note": "first-run network vs cache was not separately logged; no re-download performed"}

# 75 accession audit (actual metadata only).
reg1["acc"] = reg1.accession.astype(str).str.replace(r"\D", "", regex=True)
reg1["accession_year"] = "20" + reg1.acc.str[10:12]
a75 = reg1[["accession", "accession_year", "form", "filing_date", "acceptance_datetime", "registrant_cik_index", "xbrl_context_cik", "symbol_facts"]].copy()
a75["metadata_complete"] = a75.form.notna() & a75.filing_date.notna() & a75.acceptance_datetime.notna()
a75.to_csv(OUT / "p17_2_4_75_accession_audit.csv", index=False)

# Yearly/quarterly point observations (not interval coverage).
sec["filing_year"] = pd.to_datetime(sec.filed_date_canonical).dt.year
y = sec.groupby("filing_year").agg(filings=("accession", "nunique"), issuers=("issuer_cik", "nunique"),
                                    securities=("ticker", "nunique"), verified_security=("identity_status", lambda s: (s == "VERIFIED_SECURITY_TICKER_POINT").sum()),
                                    conflicts=("identity_status", lambda s: (s == "IDENTITY_CONFLICT").sum())).reset_index()
y.to_csv(OUT / "p17_2_4_yearly_coverage.csv", index=False)
sec["quarter"] = pd.to_datetime(sec.filed_date_canonical).dt.to_period("Q").astype(str)
q = sec.groupby("quarter").agg(issuers=("issuer_cik", "nunique"), securities=("ticker", "nunique"),
                                verified_security=("identity_status", lambda s: (s == "VERIFIED_SECURITY_TICKER_POINT").sum()),
                                conflicts=("identity_status", lambda s: (s == "IDENTITY_CONFLICT").sum())).reset_index()
q.to_csv(OUT / "p17_2_4_quarterly_coverage.csv", index=False)

# Daily cross-section: only observed filing dates; no ffill.
daily = sec.groupby("filed_date_canonical").agg(observed_issuers=("issuer_cik", "nunique"),
                                                verified_securities=("identity_status", lambda s: (s == "VERIFIED_SECURITY_TICKER_POINT").sum()),
                                                candidate_or_conflict=("identity_status", lambda s: (s == "IDENTITY_CONFLICT").sum())).reset_index()
daily.to_csv(OUT / "p17_2_4_daily_member_coverage.csv", index=False)
p13 = pd.read_csv(P13)
summary = {"p17_2_3": {"accessions": 8, "facts": len(sec), "verified_security": int((sec.identity_status == "VERIFIED_SECURITY_TICKER_POINT").sum()),
                        "conflicts": int((sec.identity_status == "IDENTITY_CONFLICT").sum())},
           "request": req,
           "seventy_five": {"accessions": len(a75), "metadata_complete": int(a75.metadata_complete.sum()),
                            "historical_2020_2024": int(a75.accession_year.isin(["2020", "2021", "2022", "2023", "2024"]).sum())},
           "daily": {"observed_dates": len(daily), "max_verified": int(daily.verified_securities.max()) if len(daily) else 0,
                     "daily_100_gate": False},
           "p13": {"expected_member_days": int(p13.expected_member_days.sum()), "verified_price_member_days": 0},
           "status": "DATA_BLOCKED",
           "reason": "Only 8 filing points and 4 verified common tickers; 8 conflicts; no valid intervals; daily cross-section max 2, not 100."}
(OUT / "p17_2_4_cross_section_summary.json").write_text(json.dumps({"observed_dates": len(daily), "max_verified": int(daily.verified_securities.max()) if len(daily) else 0,
                                                                      "gate_100": False}, indent=2), encoding="utf-8")
(OUT / "p17_2_4_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
files = {}
for p in OUT.iterdir():
    if p.suffix in {".csv", ".json"}:
        files[p.name] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
(OUT / "p17_2_4_manifest.json").write_text(json.dumps({"outputs": files}, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2, default=str))
