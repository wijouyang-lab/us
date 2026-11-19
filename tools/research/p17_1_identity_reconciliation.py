#!/usr/bin/env python3
"""P17.1 historical identity reconciliation, no fundamental alpha."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

OUT = Path("data/research/p17_1"); OUT.mkdir(parents=True, exist_ok=True)
P13 = Path("../_us_p131/data/research/p13_1/p13_1_stock_coverage.csv")
P10 = Path("../_us_audit/p10/data/research/p10_5_2_verified_identity_crosswalk.csv")
P390 = Path("data/research/p17_1_p390_source.csv")
SEC = Path("../_us_audit/fund_p63/universe/sec_fundamentals_panel_p63.csv.gz")

cov = pd.read_csv(P13)
p10 = pd.read_csv(P10)
p390 = pd.read_csv(P390)
p390["ticker"] = p390.ticker.str.strip()
p10["ticker"] = p10.ticker.str.strip()
cov["ticker"] = cov.ticker.str.strip()

# P390 reconciliation: exact ticker, member-day weights and source confidence.
m = p390.merge(cov[["ticker", "expected_member_days", "observed_member_days"]], on="ticker", how="left")
m["in_p13"] = m.expected_member_days.notna()
m["source_confidence"] = m.identity_confidence.fillna("UNKNOWN")
m["reviewed_identity_status"] = m.source_confidence.map({"high": "CANDIDATE_HIGH", "medium": "CANDIDATE_MEDIUM"}).fillna("UNRESOLVED")
m["candidate_cik"] = m.cik.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(10)
m.to_csv(OUT / "p17_1_p390_identity_reconciliation.csv", index=False)

overlap = m[m.in_p13].copy()
summary390 = {"source_rows": int(len(m)), "overlap_tickers": int(len(overlap)),
              "overlap_high": int((overlap.source_confidence == "high").sum()),
              "overlap_medium": int((overlap.source_confidence == "medium").sum()),
              "overlap_expected_member_days": int(overlap.expected_member_days.sum()),
              "high_expected_member_days": int(overlap[overlap.source_confidence == "high"].expected_member_days.sum()),
              "medium_expected_member_days": int(overlap[overlap.source_confidence == "medium"].expected_member_days.sum()),
              "overlap_observed_member_days": int(overlap.observed_member_days.sum()),
              "high_observed_member_days": int(overlap[overlap.source_confidence == "high"].observed_member_days.sum()),
              "medium_observed_member_days": int(overlap[overlap.source_confidence == "medium"].observed_member_days.sum())}

# P10 reconciliation.
p10["candidate_cik"] = p10.v2_ciks.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(10)
p10["in_p13"] = p10.ticker.isin(cov.ticker)
p10["reviewed_identity_status"] = p10.verified_status.fillna("UNRESOLVED")
p10.to_csv(OUT / "p17_1_p10_crosswalk_reconciliation.csv", index=False)

# Build conservative intervals: only membership interval + source candidate.
intervals = []
for _, r in m[m.in_p13].iterrows():
    intervals.append({"security_id": f"{r.ticker}:{r.candidate_cik}",
        "ticker": r.ticker, "cik": r.candidate_cik, "issuer_name": r.company_name,
        "security_class": "", "exchange": "", "valid_from": r.membership_added,
        "valid_to": r.membership_removed, "evidence_filed_date": r.latest_relevant_filing,
        "pit_available_date": r.announcement_available_date, "accession_number": "",
        "form": "", "evidence_source": "PR390", "source_commit": "fb39cff3",
        "identity_status": r.reviewed_identity_status, "confidence": r.source_confidence,
        "validity_basis": "membership_interval_only", "ticker_reuse_flag": "",
        "share_class_flag": "", "alias_group": "", "notes": r.evidence})
pd.DataFrame(intervals).to_csv(OUT / "p17_1_security_identity_intervals.csv", index=False)

# Conflicts / aliases.
alias = pd.DataFrame([
    {"ticker": "COG", "cik": "0000858470", "alias_group": "COG/CTRA", "note": "same issuer; separate ticker periods/classes not proven"},
    {"ticker": "CTRA", "cik": "0000858470", "alias_group": "COG/CTRA", "note": "same CIK does not prove same security"},
    {"ticker": "DISCA", "cik": "0001437107", "alias_group": "DISCA/DISCK/WBD", "note": "share classes and subsequent ticker; separate security_id"},
    {"ticker": "DISCK", "cik": "0001437107", "alias_group": "DISCA/DISCK/WBD", "note": "share class"},
    {"ticker": "WBD", "cik": "0001437107", "alias_group": "DISCA/DISCK/WBD", "note": "successor ticker; interval not fully proven"},
])
alias.to_csv(OUT / "p17_1_security_class_aliases.csv", index=False)
alias.to_csv(OUT / "p17_1_identity_conflicts.csv", index=False)

# SEC tag audit.
sec = pd.read_csv(SEC, usecols=["cik", "tickers", "metric", "taxonomy", "tag", "filed", "pit_available_date", "form"])
tag = sec.groupby(["taxonomy", "tag"]).size().reset_index(name="rows").sort_values("rows", ascending=False)
tag.to_csv(OUT / "p17_1_sec_dei_tag_audit.csv", index=False)
dei = tag[tag.taxonomy == "dei"]
facts = {"rows": int(len(sec)), "ciks": int(sec.cik.nunique()), "tickers_field_unique": int(sec.tickers.nunique()),
         "metrics": int(sec.metric.nunique()), "taxonomies": sec.taxonomy.value_counts().to_dict(),
         "dei_tags": dei.tag.tolist(), "has_trading_symbol": any("TradingSymbol" in str(x) for x in dei.tag),
         "has_security_exchange": any("SecurityExchange" in str(x) for x in dei.tag),
         "null_pit": int(pd.to_datetime(sec.pit_available_date, errors="coerce").isna().sum()),
         "min_pit": str(pd.to_datetime(sec.pit_available_date, errors="coerce").min().date()),
         "max_pit": str(pd.to_datetime(sec.pit_available_date, errors="coerce").max().date())}
pd.DataFrame([facts]).to_csv(OUT / "p17_1_sec_facts_full_audit.csv", index=False)

# Coverage: conservative verified is only P10 IDENTITY_CONFIRMED with price.
verified = p10[(p10.reviewed_identity_status == "IDENTITY_CONFIRMED") & p10.in_p13]
verified_tickers = set(verified.ticker)
candidate_tickers = set(m[m.in_p13].ticker)
v = cov[cov.ticker.isin(verified_tickers)]
c = cov[cov.ticker.isin(candidate_tickers)]
full = {"expected_tickers": 607, "expected_member_days": int(cov.expected_member_days.sum()),
        "verified_identity_tickers": len(verified_tickers), "verified_member_days": int(v.expected_member_days.sum()),
        "verified_observed_member_days": int(v.observed_member_days.sum()),
        "candidate_high_tickers": len(candidate_tickers),
        "candidate_high_member_days": int(c.expected_member_days.sum()),
        "candidate_high_observed_member_days": int(c.observed_member_days.sum()),
        "unresolved_tickers": int(607 - len(candidate_tickers | verified_tickers))}
priced = cov[cov.observed_member_days > 0]
priced_candidate = priced[priced.ticker.isin(candidate_tickers | verified_tickers)]
priced_verified = priced[priced.ticker.isin(verified_tickers)]
priced_cov = {"priced_tickers": int(len(priced)), "priced_member_days": int(priced.observed_member_days.sum()),
              "verified_price_tickers": int(len(priced_verified)),
              "verified_price_member_days": int(priced_verified.observed_member_days.sum()),
              "candidate_price_tickers": int(len(priced_candidate)),
              "candidate_price_member_days": int(priced_candidate.observed_member_days.sum()),
              "daily_cross_section_max_candidate": int(len(priced_candidate)),
              "exploratory_100_names_gate": bool(len(priced_candidate) >= 100)}
pd.DataFrame([full]).to_csv(OUT / "p17_1_identity_coverage_full.csv", index=False)
pd.DataFrame([priced_cov]).to_csv(OUT / "p17_1_identity_coverage_priced.csv", index=False)
# Annual: approximate no annual file from source; write empty with status.
pd.DataFrame([{"status": "ANNUAL_DATA_BLOCKED", "reason": "no dated identity intervals for full priced universe"}]).to_csv(OUT / "p17_1_identity_coverage_annual.csv", index=False)
pd.DataFrame([{"status": "INDUSTRY_DATA_BLOCKED"}]).to_csv(OUT / "p17_1_identity_coverage_industry.csv", index=False)
pd.DataFrame([{"ticker": t} for t in sorted(set(priced.ticker) - set(priced_candidate.ticker))]).to_csv(OUT / "p17_1_unresolved_priced_tickers.csv", index=False)

summary = {"p390": summary390, "p10_rows": int(len(p10)), "p10_in_p13": int(p10.in_p13.sum()),
           "p10_confirmed_in_p13": int((p10.reviewed_identity_status == "IDENTITY_CONFIRMED").sum()),
           "sec_facts": facts, "coverage_full": full, "coverage_priced": priced_cov,
           "status": "DATA_BLOCKED",
           "reason": "Only 2 verified identities in P13, both without prices; 54 PR390 candidates cannot prove historical intervals; priced candidate max 54 < 100/day gate."}
(OUT / "p17_1_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
files = {}
for p in OUT.iterdir():
    if p.suffix in {".csv", ".json"}:
        files[p.name] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size, "rows": len(pd.read_csv(p)) if p.suffix == ".csv" else None}
(out := OUT / "p17_1_manifest.json").write_text(json.dumps({"outputs": files,
    "sources": {"p390_commit": "fb39cff3", "p390_sha256": hashlib.sha256(P390.read_bytes()).hexdigest(),
                "p10_sha256": hashlib.sha256(P10.read_bytes()).hexdigest()},
    "note": "P17.1 identity reconciliation; no alpha/backtest"}, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2, default=str))
