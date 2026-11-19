#!/usr/bin/env python3
"""P17 PIT identity / SEC facts audit. Stops before fundamental backtest if identity fails."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

OUT = Path("data/research/p17")
OUT.mkdir(parents=True, exist_ok=True)
P13 = Path("../_us_p131/data/research/p13_1/p13_1_stock_coverage.csv")
ID = Path("../_us_audit/p10/data/research/p10_5_2_verified_identity_crosswalk.csv")
CONFLICT = Path("../_us_audit/p10/data/research/p10_5_3_historical_ticker_identity.csv")
SEC = Path("../_us_audit/fund_p63/universe/sec_fundamentals_panel_p63.csv.gz")
SPY = Path("../_us_audit/pr512/data/research/p9_1_support_resistance/SPY.csv")

cov = pd.read_csv(P13)
idm = pd.read_csv(ID)
conf = pd.read_csv(CONFLICT)
status_map = dict(zip(idm.ticker, idm.verified_status))
cik_map = dict(zip(idm.ticker, idm.v2_ciks))
cov["status"] = cov.ticker.map(status_map).fillna("UNRESOLVED")
cov["cik"] = cov.ticker.map(cik_map)
cov.to_csv(OUT / "p17_security_identity.csv", index=False)
conf.to_csv(OUT / "p17_identity_conflicts.csv", index=False)
idm.to_csv(OUT / "p17_identity_evidence.csv", index=False)
weighted = cov.groupby("status").expected_member_days.sum().to_dict()
total = int(cov.expected_member_days.sum())
coverage = {"expected_member_days": total, "by_status": {k: int(v) for k, v in weighted.items()},
            "verified_member_day_rate": float(weighted.get("IDENTITY_CONFIRMED", 0) / total),
            "high_or_better_rate": float((weighted.get("IDENTITY_CONFIRMED", 0) + weighted.get("IDENTITY_PARTIAL", 0)) / total),
            "unique_tickers": int(cov.ticker.nunique()), "mapped_tickers": int(cov.status.ne("UNRESOLVED").sum()),
            "unique_ciks": int(cov.cik.dropna().nunique()),
            "identity_conflicts": int((cov.status == "IDENTITY_CONFLICT").sum()),
            "status": "DATA_BLOCKED",
            "note": "P10 crosswalk covers 80 historical names; most P13 members have no verified PIT identity."}
(OUT / "p17_identity_coverage.json").write_text(json.dumps(coverage, indent=2), encoding="utf-8")

# SEC facts audit (existence, PIT field; no identity join used for alpha)
sec = pd.read_csv(SEC, usecols=["cik", "tickers", "metric", "taxonomy", "filed", "pit_available_date", "form", "value"])
sec["pit_available_date"] = pd.to_datetime(sec.pit_available_date, errors="coerce")
facts = {"rows": len(sec), "ciks": int(sec.cik.nunique()), "tickers": int(sec.tickers.nunique()),
         "metrics": int(sec.metric.nunique()), "taxonomies": sec.taxonomy.value_counts().to_dict(),
         "forms": sec.form.value_counts().head(8).to_dict(),
         "min_pit": str(sec.pit_available_date.min().date()), "max_pit": str(sec.pit_available_date.max().date()),
         "null_pit": int(sec.pit_available_date.isna().sum()),
         "status": "AVAILABLE_BUT_IDENTITY_BLOCKED"}
(OUT / "p17_sec_facts_audit.csv").write_text(pd.DataFrame([facts]).to_csv(index=False), encoding="utf-8")

# Regime audit for P16: full series vs 2020-2024.
spy = pd.read_csv(SPY, usecols=["Date", "close"]); spy["date"] = pd.to_datetime(spy.Date, utc=True).dt.tz_convert(None).dt.normalize()
spy = spy.drop_duplicates("date").set_index("date")["close"].sort_index()
reg = spy > spy.rolling(200).mean()
main = reg[(reg.index >= "2020-01-02") & (reg.index <= "2024-12-31")]
three = reg[(reg.index >= "2022-01-03") & (reg.index <= "2024-12-31")]
audit = {"p16_full_risk_on": int(reg.sum()), "p16_full_days": int(reg.notna().sum()),
         "main_risk_on": int(main.sum()), "main_days": int(main.notna().sum()),
         "three_risk_on": int(three.sum()), "three_days": int(three.notna().sum()),
         "spy_missing_weekdays": int(len(pd.bdate_range(spy.index.min(), spy.index.max())) - len(spy)),
         "ranking_issue": "IC uses rank(MOM63)+rank(MOM126); portfolio uses raw MOM63+MOM126",
         "price_basis": "stocks adjusted_close; SPY close (mismatch)",
         "sharpe_issue": "P16 uses CAGR/vol, not daily excess return",
         "regime_scope": "entry filter only; existing holdings not reduced",
         "status": "P16_ENGINE_AUDIT_PARTIAL"}
(OUT / "p16_engine_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
summary = {"overall": "DATA_BLOCKED", "identity": coverage, "sec_facts": facts, "p16_audit": audit,
           "entry": "NOT_RUN_IDENTITY_BLOCKED", "exit": "NOT_RUN_IDENTITY_BLOCKED",
           "quality": "DATA_BLOCKED", "growth": "DATA_BLOCKED", "value": "DATA_BLOCKED"
           if False else "DATA_BLOCKED", "portfolio": "NOT_RUN"}
(OUT / "p17_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
files = {}
for p in OUT.iterdir():
    if p.suffix in {".csv", ".json"}:
        files[p.name] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
(OUT / "p17_manifest.json").write_text(json.dumps({"outputs": files,
    "inputs": {str(P13): hashlib.sha256(P13.read_bytes()).hexdigest(), str(ID): hashlib.sha256(ID.read_bytes()).hexdigest()},
    "note": "DATA_BLOCKED: PIT identity not sufficient"}, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2, default=str))
