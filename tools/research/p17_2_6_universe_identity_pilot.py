#!/usr/bin/env python3
"""P17.2.6 historical universe identity pilot: 3 anchors x 100 P13 members."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("data/research/p17_2_6"); OUT.mkdir(parents=True, exist_ok=True)
PANEL = Path("../_us_p131/data/research/p13_1/p13_1_aligned_panel.csv")
COV = Path("../_us_p131/data/research/p13_1/p13_1_stock_coverage.csv")
SEC = Path("../_us_audit/fund_p63/universe/sec_fundamentals_panel_p63.csv.gz")
P25 = Path("../_us_p1725/data/research/p17_2_5/p17_2_5_ticker_security_mapping.csv")
anchors = {"A": "2020-06-30", "B": "2022-06-30", "C": "2024-06-28"}
panel = pd.read_csv(PANEL, usecols=["ticker", "signal_date"])
panel["signal_date"] = pd.to_datetime(panel.signal_date)
cov = pd.read_csv(COV)

sec = pd.read_csv(SEC, usecols=["cik", "tickers"]).drop_duplicates()
cik_map = {}
for _, r in sec.iterrows():
    if isinstance(r.tickers, str):
        for t in r.tickers.split(","):
            t = t.strip()
            if t:
                cik_map.setdefault(t, str(r.cik).split(".")[0].zfill(10))

rows = []
for label, date in anchors.items():
    members = panel[panel.signal_date == date].ticker.unique()
    d = pd.DataFrame({"ticker": members, "anchor": label, "anchor_date": date})
    d = d.merge(cov[["ticker", "expected_member_days", "observed_member_days", "coverage", "first_expected_date", "last_expected_date"]], on="ticker", how="left")
    d["coverage"] = d.coverage.fillna(0)
    d["stratum"] = np.where(d.coverage >= .95, "HIGH_PRICE_COVERAGE", "LOW_PRICE_COVERAGE")
    d["listed_after_2020"] = d.first_expected_date.astype(str) > "2020-01-01"
    d["removed_before_end"] = d.last_expected_date.astype(str) < "2024-12-31"
    d["hash"] = [hashlib.sha256(f"{date}:{t}".encode()).hexdigest() for t in d.ticker]
    selected = []
    groups = list(d.groupby(["stratum", "listed_after_2020", "removed_before_end"]))
    idx = 0
    while len(selected) < 100 and any(len(g) > 0 for _, g in groups):
        for _, g in groups:
            g = g.sort_values("hash")
            if idx < len(g) and len(selected) < 100:
                selected.append(g.iloc[idx])
        idx += 1
    s = pd.DataFrame(selected).head(100)
    s["cik_candidate"] = s.ticker.map(cik_map)
    s["cik_status"] = np.where(s.cik_candidate.notna(), "CANDIDATE_CURRENT_ONLY", "NO_CIK_CANDIDATE")
    s["sample_reason"] = "deterministic stratified hash by price coverage / later listing / removal"
    rows.append(s)
sample = pd.concat(rows, ignore_index=True)
sample.to_csv(OUT / "p17_2_6_sample_manifest.csv", index=False)

# Current CIK candidates only; not historical proof.
cand = sample[["anchor", "anchor_date", "ticker", "cik_candidate", "cik_status"]].copy()
cand.to_csv(OUT / "p17_2_6_ticker_cik_candidates.csv", index=False)

# Existing verified points used as the only XBRL evidence. No new 300-filing download.
p25 = pd.read_csv(P25, dtype=str)
p25["acceptance_utc"] = pd.to_datetime(p25.acceptance_raw, format="%Y%m%d%H%M%S", errors="coerce", utc=True)
asof = []
for _, r in sample.iterrows():
    hits = p25[(p25.ticker == r.ticker) & (p25.acceptance_utc <= pd.Timestamp(r.anchor_date, tz="UTC"))]
    if len(hits):
        h = hits.sort_values("acceptance_utc").iloc[-1]
        age = (pd.Timestamp(r.anchor_date, tz="UTC") - h.acceptance_utc).days
        asof.append({"anchor": r.anchor, "ticker": r.ticker, "evidence_accession": h.accession,
                     "evidence_title": h.security_title, "evidence_time": h.acceptance_utc,
                     "evidence_age_days": age, "status": "ASOF_EVIDENCE_AVAILABLE" if age <= 400 else "STALE_OR_UNCONFIRMED"})
    else:
        asof.append({"anchor": r.anchor, "ticker": r.ticker, "evidence_accession": "", "evidence_title": "",
                     "evidence_time": "", "evidence_age_days": None, "status": "NO_ASOF_EVIDENCE"})
asofdf = pd.DataFrame(asof); asofdf.to_csv(OUT / "p17_2_6_asof_evidence.csv", index=False)
asofdf[asofdf.status == "STALE_OR_UNCONFIRMED"].to_csv(OUT / "p17_2_6_stale_evidence.csv", index=False)
pd.DataFrame([{"status": "NONE", "reason": "no new 300-filing extraction performed"}]).to_csv(OUT / "p17_2_6_identity_conflicts.csv", index=False)
pd.DataFrame([{"request_type": "SEC", "network": 0, "cache": 0, "note": "no new SEC requests; scope stopped at current CIK/evidence audit"}]).to_csv(OUT / "p17_2_6_request_audit.csv", index=False)

anchor = []
for label, date in anchors.items():
    s = sample[sample.anchor == label]
    a = asofdf[asofdf.anchor == label]
    anchor.append({"anchor": label, "date": date, "expected_members": int((panel.signal_date == date).sum()),
                   "sampled": len(s), "cik_candidates": int(s.cik_candidate.notna().sum()),
                   "verified_points": int((a.status == "ASOF_EVIDENCE_AVAILABLE").sum()),
                   "asof_evidence": int((a.status == "ASOF_EVIDENCE_AVAILABLE").sum()),
                   "stale": int((a.status == "STALE_OR_UNCONFIRMED").sum()),
                   "no_evidence": int((a.status == "NO_ASOF_EVIDENCE").sum())})
adf = pd.DataFrame(anchor); adf.to_csv(OUT / "p17_2_6_anchor_coverage.csv", index=False)
# price/member join is sample-level only.
sample[["anchor", "ticker", "observed_member_days", "coverage", "cik_candidate", "cik_status"]].to_csv(OUT / "p17_2_6_price_member_join.csv", index=False)
summary = {"anchors": anchors, "expected_total": 300, "sampled_total": len(sample), "unique_tickers": int(sample.ticker.nunique()),
           "cik_candidates": int(sample.cik_candidate.notna().sum()),
           "asof_evidence": int((asofdf.status == "ASOF_EVIDENCE_AVAILABLE").sum()),
           "stale": int((asofdf.status == "STALE_OR_UNCONFIRMED").sum()),
           "no_evidence": int((asofdf.status == "NO_ASOF_EVIDENCE").sum()),
           "network_requests": 0, "status": "DATA_BLOCKED",
           "reason": "Only existing 8-filing XBRL evidence was available; 300 historical filings were not retrieved, so security identity coverage is not measured."}
(OUT / "p17_2_6_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
files = {}
for p in OUT.iterdir():
    if p.suffix in {".csv", ".json"}:
        files[p.name] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
(OUT / "p17_2_6_manifest.json").write_text(json.dumps({"outputs": files}, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
print(adf.to_string(index=False))
