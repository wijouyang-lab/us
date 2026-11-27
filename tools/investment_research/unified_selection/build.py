#!/usr/bin/env python3
"""Unified selection V1: integrate existing FS2 style ranks. Research only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = "unified.v1"
DIMS = ["value_pct", "quality_pct", "garp_pct", "trend_pct"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    src = a.root / "data/research/fs2/composite_candidates_v1.csv"
    d = pd.read_csv(src)
    d["ticker"] = d["ticker"].astype(str)
    if d.ticker.duplicated().any(): raise ValueError("duplicate ticker")
    for c in ["value_pct", "quality_pct", "garp_pct", "trend_pct"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["dimension_coverage"] = d[DIMS].notna().sum(axis=1)
    d["data_quality_status"] = np.select(
        [d.dimension_coverage == 4, d.dimension_coverage >= 2, d.dimension_coverage == 1],
        ["FULL", "PARTIAL", "MINIMAL"], default="MISSING")
    d["missing_reason"] = d.apply(lambda r: ";".join([c.replace("_pct", "").upper() + "_MISSING" for c in DIMS if pd.isna(r[c])]) or "", axis=1)
    d["composite_ready"] = (d.dimension_coverage == 4) & (~d.tradability_status.isin(["BLOCKED", "INSUFFICIENT_DATA"]))
    d["composite_score"] = d[DIMS].mean(axis=1, skipna=False)
    d.loc[~d.composite_ready, "composite_score"] = np.nan
    d["research_rank"] = np.nan
    ready = d[d.composite_ready].sort_values("composite_score", ascending=False)
    d.loc[ready.index, "research_rank"] = np.arange(1, len(ready) + 1)
    d["value_strengths"] = np.where(d.value_pct >= .8, "VALUE_TOP20", "")
    d["quality_strengths"] = np.where(d.quality_pct >= .8, "QUALITY_TOP20", "")
    d["growth_strengths"] = np.where(d.garp_pct >= .8, "GARP_TOP20", "")
    d["trend_strengths"] = np.where(d.trend_pct >= .8, "TREND_TOP20", "")
    d["risk_flags"] = d.apply(lambda r: ";".join(filter(None, [
        "CORPORATE_ACTION_REVIEW" if r.corporate_action_status == "CORPORATE_ACTION_REVIEW" else "",
        "NON_COMMON" if r.security_type != "COMMON" else "",
        "LOW_LIQUIDITY" if pd.isna(r.adv20_usd) or r.adv20_usd < 2_000_000 else "",
    ])) or "", axis=1)
    def group(r):
        if r.tradability_status in ("BLOCKED", "INSUFFICIENT_DATA"): return "BLOCKED"
        if not r.composite_ready: return "TIER_C"
        if r.composite_score >= .80 and r.style_count >= 2: return "TIER_A"
        if r.composite_score >= .60: return "TIER_B"
        return "TIER_C"
    d["research_group"] = d.apply(group, axis=1)
    d["research_status"] = np.where(d.research_group == "BLOCKED", "BLOCKED", "ELIGIBLE_FOR_RESEARCH")
    d["selection_explanation"] = d.apply(lambda r: f"{r.research_group}; styles={r.style_tags}; " + f"score={r.composite_score:.3f}" if pd.notna(r.composite_score) else f"{r.research_group}; composite not comparable; missing={r.missing_reason or 'none'}", axis=1)
    d["formula_version"] = "fs2.v1.4/unified.v1"
    d["fundamentals_as_of"] = "2026-11-05"
    d["prices_as_of"] = "2026-11-25"
    cols = ["ticker", "issuer_name", "security_type", "industry", "composite_tier", "tradability_status",
            "value_rank", "quality_rank", "garp_rank", "trend_pct", "value_pct", "quality_pct", "garp_pct",
            "dimension_coverage", "data_quality_status", "missing_reason", "composite_score", "composite_ready",
            "research_rank", "research_group", "research_status", "style_tags", "value_strengths",
            "quality_strengths", "growth_strengths", "trend_strengths", "risk_flags", "selection_explanation",
            "adv20_usd", "corporate_action_status", "formula_version", "fundamentals_as_of", "prices_as_of"]
    d = d[cols]
    d.to_csv(a.out / "unified_selection_v1.csv", index=False)
    d[d.research_group.isin(["TIER_A", "TIER_B"])].sort_values(["research_group", "research_rank"]).head(100).to_csv(a.out / "unified_top100_v1.csv", index=False)
    summary = {
        "version": VERSION, "rows": len(d), "unique_tickers": int(d.ticker.nunique()),
        "groups": d.research_group.value_counts().to_dict(),
        "data_quality": d.data_quality_status.value_counts().to_dict(),
        "composite_ready": int(d.composite_ready.sum()),
        "composite_not_ready": int((~d.composite_ready).sum()),
        "coverage": {c: int(d[c].notna().sum()) for c in DIMS},
        "fundamentals_as_of": "2026-11-05", "prices_as_of": "2026-11-25",
        "inputs": {str(src): sha(src)},
        "research_only": True,
    }
    (a.out / "unified_selection_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
