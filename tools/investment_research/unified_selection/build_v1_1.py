#!/usr/bin/env python3
"""Unified Selection V1.1: group-comparable ranking + raw metrics."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np, pandas as pd

SPECIAL = {"BANKS", "INSURANCE", "REIT", "OTHER_FINANCIALS"}


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root", type=Path, required=True); ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    root = a.root; sel = root / "data/universe/selection"
    d = pd.read_csv(root / "data/research/unified_selection/unified_selection_v1.csv")
    v = pd.read_csv(sel / "value_rankings.csv")[["ticker", "pb", "ps", "earnings_yield", "fcf_yield", "financial_period", "filed", "accn", "source_url", "data_as_of"]].drop_duplicates("ticker")
    q = pd.read_csv(sel / "quality_rankings.csv")[["ticker", "roe", "roa", "cfo_to_avg_assets", "liabilities_to_assets", "financial_period", "filed", "accn"]].drop_duplicates("ticker").add_prefix("q_").rename(columns={"q_ticker": "ticker"})
    g = pd.read_csv(sel / "garp_rankings.csv")[["ticker", "revenue_growth_1y", "eps_growth_1y", "fcf_growth_1y", "history_years", "latest_period", "filed", "accn"]].drop_duplicates("ticker").add_prefix("g_").rename(columns={"g_ticker": "ticker"})
    d = d.merge(v, on="ticker", how="left").merge(q, on="ticker", how="left").merge(g, on="ticker", how="left")
    for c in ["roe", "roa", "cfo_to_avg_assets", "liabilities_to_assets"]:
        if "q_" + c in d: d[c] = d["q_" + c]
    for c in ["revenue_growth_1y", "eps_growth_1y", "fcf_growth_1y"]:
        if "g_" + c in d: d[c] = d["g_" + c]
    # trend raw returns
    px = pd.read_csv(root / "data/universe/price_liquidity/price_cache_v1.csv.gz", usecols=["ticker", "date", "raw_close"])
    px["date"] = pd.to_datetime(px.date, errors="coerce"); px = px.dropna().sort_values(["ticker", "date"])
    rows = []
    for t, x in px.groupby("ticker"):
        c = x.raw_close.astype(float)
        rows.append({"ticker": t, "ret20": c.iloc[-1] / c.iloc[-21] - 1 if len(c) >= 21 else np.nan,
                     "ret60": c.iloc[-1] / c.iloc[-61] - 1 if len(c) >= 61 else np.nan,
                     "ma20": c.tail(20).mean() if len(c) >= 20 else np.nan, "ma60": c.tail(60).mean() if len(c) >= 60 else np.nan})
    d = d.merge(pd.DataFrame(rows), on="ticker", how="left")
    d["special_industry"] = d.industry.isin(SPECIAL)
    d["comparable_group"] = d.security_type.fillna("UNKNOWN") + "|" + d.industry.fillna("UNCLASSIFIED") + "|" + np.where(d.special_industry, "SPECIAL_FINANCIAL", "STANDARD")
    d["group_total_n"] = d.groupby("comparable_group").comparable_group.transform("size")
    d["group_eligible_n"] = d.groupby("comparable_group").composite_ready.transform("sum").astype(int)
    d["group_rank"] = np.nan
    eligible = d[d.composite_ready & (d.group_eligible_n >= 20)].copy()
    eligible["group_rank"] = eligible.groupby("comparable_group").composite_score.rank(ascending=False, method="first")
    d.loc[eligible.index, "group_rank"] = eligible["group_rank"]
    # New research rank is group rank only; old cross-sectional rank is retained explicitly as legacy.
    d["legacy_research_rank"] = d["research_rank"]; d["research_rank"] = d["group_rank"]
    d["composite_status"] = np.where(d.composite_ready & (d.group_eligible_n >= 20), "GROUP_COMPARABLE_DISPLAY_ONLY", "NOT_COMPARABLE")
    d["composite_legacy_not_comparable"] = True
    def grp(r):
        if r.tradability_status in ("BLOCKED", "INSUFFICIENT_DATA"): return "BLOCKED"
        if r.composite_status != "GROUP_COMPARABLE_DISPLAY_ONLY": return "TIER_C"
        if r.group_rank <= 5 and r.dimension_coverage == 4 and (pd.isna(r.risk_flags) or r.risk_flags == ""): return "TIER_A"
        if r.group_rank <= 20: return "TIER_B"
        return "TIER_C"
    d["research_group"] = d.apply(grp, axis=1)
    d["research_status"] = np.where(d.research_group == "BLOCKED", "BLOCKED", "ELIGIBLE_FOR_RESEARCH")
    d["selection_explanation"] = d.apply(lambda r: f"{r.research_group}; group_eligible={r.group_eligible_n}; composite={r.composite_status}; score={r.composite_score:.3f}" if pd.notna(r.composite_score) else f"{r.research_group}; NOT_COMPARABLE; missing={r.missing_reason or 'none'}", axis=1)
    d["fundamentals_as_of"] = "2026-11-05"; d["prices_as_of"] = "2026-11-25"
    # raw / traceability fields
    for c in ["pb", "ps", "earnings_yield", "fcf_yield", "roe", "roa", "cfo_to_avg_assets", "liabilities_to_assets",
              "revenue_growth_1y", "eps_growth_1y", "fcf_growth_1y", "ret20", "ret60", "ma20", "ma60"]:
        if c not in d: d[c] = np.nan
    d["pe"] = np.nan; d["pe_reason"] = "UNAVAILABLE_NOT_IN_SOURCE_RANKING"
    def clean(v):
        if pd.isna(v): return "UNKNOWN"
        s = str(v).strip()
        return s if s and s.lower() != "nan" else "UNKNOWN"
    d["fundamental_source"] = d.source_url.map(clean)
    d["fiscal_period"] = d.financial_period.combine_first(d.q_financial_period).combine_first(d.g_latest_period).map(clean)
    d["filing_date"] = d.filed.combine_first(d.q_filed).combine_first(d.g_filed).map(clean)
    d["accession"] = d.accn.combine_first(d.q_accn).combine_first(d.g_accn).map(clean)
    d["revision_status"] = "UNKNOWN"
    d["price_source"] = "YFINANCE_RAW_CLOSE"; d["adjustment_status"] = "UNADJUSTED"; d["price_as_of"] = "2026-11-25"
    d["forward_eps"] = "UNAVAILABLE"; d["peg"] = "UNAVAILABLE"
    d["value_raw"] = d.apply(lambda r: f"PB={r.pb};PS={r.ps};EY={r.earnings_yield};FCFY={r.fcf_yield};PE=UNAVAILABLE", axis=1)
    d["quality_raw"] = d.apply(lambda r: f"ROE={r.roe};ROA={r.roa};CFO/A={r.cfo_to_avg_assets};L/A={r.liabilities_to_assets}", axis=1)
    d["growth_raw"] = d.apply(lambda r: f"Rev1Y={r.revenue_growth_1y};EPS1Y={r.eps_growth_1y};FCF1Y={r.fcf_growth_1y};years={r.g_history_years};FORWARD_GROWTH_UNAVAILABLE", axis=1)
    d["trend_raw"] = d.apply(lambda r: f"20D={r.ret20};60D={r.ret60};MA20={r.ma20};MA60={r.ma60};RAW_PRICE_RESEARCH_ONLY", axis=1)
    d.to_csv(a.out / "unified_selection_v1_1.csv", index=False)
    d[d.research_group.isin(["TIER_A", "TIER_B"])].sort_values(["research_group", "group_rank"]).head(100).to_csv(a.out / "unified_top100_v1_1.csv", index=False)
    summary = {"version": "unified.v1.1", "rows": len(d), "groups": d.research_group.value_counts().to_dict(),
               "composite_status": d.composite_status.value_counts().to_dict(), "comparable_groups": int(d.comparable_group.nunique()),
               "groups_total": int(d.comparable_group.nunique()),
               "groups_eligible_20plus": int((d.groupby("comparable_group").group_eligible_n.first() >= 20).sum()),
               "ranked_rows": int(d.research_rank.notna().sum()),
               "unknown_counts": {c: int((d[c] == "UNKNOWN").sum()) for c in ["fundamental_source", "fiscal_period", "filing_date", "accession"]},
               "special_industry_rows": int(d.special_industry.sum()),
               "raw_coverage": {c: int(d[c].notna().sum()) for c in ["pb", "ps", "earnings_yield", "fcf_yield", "roe", "roa", "cfo_to_avg_assets", "liabilities_to_assets", "revenue_growth_1y", "eps_growth_1y", "fcf_growth_1y"]},
               "input_sha": {"unified_v1": sha(root / "data/research/unified_selection/unified_selection_v1.csv")},
               "research_only": True}
    (a.out / "unified_selection_v1_1_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
