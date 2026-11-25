#!/usr/bin/env python3
"""FS-2 research composite candidate engine, no production linkage."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

STYLE_CUT = 0.20
MIN_ADV = 2_000_000
MIN_DAYS = 20
MAX_AGE = 7


def pct_rank(s):
    s = pd.to_numeric(s, errors="coerce")
    return s.rank(pct=True, ascending=True)


def trend_features(px: pd.DataFrame):
    px = px.sort_values("date")
    close = px.raw_close.astype(float)
    if len(close) < 60: return None
    last = close.iloc[-1]
    r20 = last / close.iloc[-21] - 1
    r60 = last / close.iloc[-61] - 1
    ma20 = close.tail(20).mean(); ma60 = close.tail(60).mean()
    high60 = close.tail(60).max()
    dd = last / high60 - 1
    score = (1 if r20 > 0 else -1) + (1 if r60 > 0 else -1) + (1 if last > ma20 else -1) + (1 if ma20 > ma60 else -1) - (1 if dd < -0.15 else 0)
    return {"r20": r20, "r60": r60, "ma20": ma20, "ma60": ma60, "dd60": dd, "trend_score": score}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    root = a.root
    sel = root / "data/universe/selection"
    pl = root / "data/universe/price_liquidity"
    uni = pd.read_csv(pl / "universe_identity_v1.csv", dtype=str)
    uni = uni[uni.ticker_status == "VALID"].drop_duplicates("ticker")
    ranks = {
        "value": (pd.read_csv(sel / "value_rankings.csv"), "value_rank"),
        "quality": (pd.read_csv(sel / "quality_rankings.csv"), "quality_rank"),
        "garp": (pd.read_csv(sel / "garp_rankings.csv"), "garp_rank"),
    }
    base = uni[["ticker", "cik", "issuer_name", "security_type", "exchange"]].copy()
    for name, (d, col) in ranks.items():
        d = d[["ticker", col]].drop_duplicates("ticker")
        d.columns = ["ticker", f"{name}_rank"]
        base = base.merge(d, on="ticker", how="left")
    # price/trend
    px = pd.read_csv(pl / "price_cache_v1.csv.gz")
    px["date"] = pd.to_datetime(px.date, errors="coerce")
    liq = pd.read_csv(pl / "liquidity_metrics_v1.csv")
    base = base.merge(liq, on="ticker", how="left")
    trends = []
    for t, g in px.groupby("ticker"):
        f = trend_features(g)
        if f: f["ticker"] = t; trends.append(f)
    tr = pd.DataFrame(trends)
    base = base.merge(tr, on="ticker", how="left")
    # tradability
    base["sec_type"] = base.security_type.fillna("UNKNOWN")
    base["has_price"] = base.valid_days.fillna(0) >= MIN_DAYS
    base["has_60"] = base.valid_days.fillna(0) >= 60
    base["adv_ok"] = base.adv20_usd.fillna(0) >= MIN_ADV
    base["ca_ok"] = base.corporate_action_status.eq("OK").fillna(False)
    base["fresh"] = base.data_age_days.fillna(999) <= MAX_AGE
    base["identity_ok"] = base.sec_type.isin(["COMMON", "ADR"]) & base.cik.notna()
    def status(r):
        if not r.identity_ok: return "BLOCKED", "IDENTITY_NOT_COMMON_OR_ADR"
        if r.sec_type != "COMMON": return "WATCH", "ADR_SEPARATE_CATEGORY"
        if not r.ca_ok: return "BLOCKED", "CORPORATE_ACTION_REVIEW"
        if not r.has_price: return "INSUFFICIENT_DATA", "PRICE_20D_MISSING"
        if not r.adv_ok: return "BLOCKED", "LIQUIDITY_BELOW_RESEARCH_FLOOR"
        if not r.fresh: return "WATCH", "PRICE_STALE"
        if not r.has_60: return "WATCH", "PRICE_60D_MISSING"
        return "ELIGIBLE_FOR_RESEARCH", ""
    st = base.apply(status, axis=1, result_type="expand"); base["tradability_status"] = st[0]; base["tradability_reason"] = st[1]
    # style percentile and flags
    style_cols = []
    for name in ["value", "quality", "garp"]:
        c = f"{name}_rank"; p = f"{name}_pct"; style_cols.append(p)
        base[p] = 1 - base[c] / base[c].max()
        base[f"{name}_top20"] = base[c] <= base[c].quantile(STYLE_CUT)
    base["trend_pct"] = pct_rank(base.trend_score)
    base["trend_top20"] = base.trend_pct >= 1 - STYLE_CUT
    base["style_count"] = base[["value_top20", "quality_top20", "garp_top20", "trend_top20"]].sum(axis=1)
    for name in ["value", "quality", "garp", "trend"]:
        p = base[f"{name}_pct"].fillna(0)
        base[f"{name}_tag"] = np.where(base[f"{name}_top20"], name.upper() + "_CANDIDATE", "")
    def tier(r):
        if r.tradability_status == "BLOCKED": return "BLOCKED"
        if r.tradability_status == "INSUFFICIENT_DATA": return "WATCH"
        if r.style_count >= 2 and r.tradability_status == "ELIGIBLE_FOR_RESEARCH": return "TIER_1"
        if r.style_count >= 1 and r.tradability_status == "ELIGIBLE_FOR_RESEARCH": return "TIER_2"
        if r.style_count >= 1: return "WATCH"
        return "WATCH"
    base["composite_tier"] = base.apply(tier, axis=1)
    base["multi_style"] = base.style_count >= 2
    base["style_tags"] = base[["value_tag", "quality_tag", "garp_tag", "trend_tag"]].apply(lambda r: ";".join([x for x in r if x]), axis=1)
    base["primary_reason"] = base.apply(lambda r: f"styles={r.style_count};{r.style_tags};tradability={r.tradability_status}", axis=1)
    # candidate files: all ranked rows, ranked by style rank
    for name in ["value", "quality", "garp"]:
        c = f"{name}_rank"
        d = base[base[c].notna()].sort_values(c)
        d.to_csv(a.out / f"{name}_candidates_v1.csv", index=False)
    base[base.trend_top20].sort_values("trend_pct", ascending=False).to_csv(a.out / "trend_candidates_v1.csv", index=False)
    base.to_csv(a.out / "composite_candidates_v1.csv", index=False)
    base[base.composite_tier.isin(["TIER_1", "TIER_2"])].to_csv(a.out / "composite_shortlist_v1.csv", index=False)
    base[["ticker", "tradability_status", "tradability_reason", "adv20_usd", "valid_days", "corporate_action_status"]].to_csv(a.out / "tradability_decisions_v1.csv", index=False)
    summary = {
        "universe": len(base), "value_candidates": int(base.value_top20.sum()), "quality_candidates": int(base.quality_top20.sum()),
        "garp_candidates": int(base.garp_top20.sum()), "trend_candidates": int(base.trend_top20.sum()),
        "multi_style": int(base.multi_style.sum()),
        "tiers": base.composite_tier.value_counts().to_dict(),
        "tradability": base.tradability_status.value_counts().to_dict(),
        "blocked_ca": int((base.tradability_reason == "CORPORATE_ACTION_REVIEW").sum()),
        "missing_price": int((~base.has_price).sum()),
        "eligible": int((base.tradability_status == "ELIGIBLE_FOR_RESEARCH").sum()),
        "research_only": True,
    }
    (a.out / "fs2_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
