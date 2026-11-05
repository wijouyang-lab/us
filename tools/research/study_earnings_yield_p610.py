"""P6.10 standalone Earnings Yield V1 study.

Current cross-section only; no historical return test because P6.7 PIT gates
remain failed. No composite score or production use.
"""
from __future__ import annotations
import argparse, csv, json, math
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

RANK = Path("data/universe/value_metric_rankings_p69.csv")
P68 = Path("data/universe/value_v1_readiness_p68.csv")
QUALITY = Path("data/universe/quality_v1_scores_p66.csv")
OUT_SCORES = Path("data/universe/earnings_yield_v1_scores_p610.csv")
OUT_COV = Path("data/universe/earnings_yield_coverage_p610.json")
OUT_CORR = Path("data/universe/earnings_yield_correlation_p610.json")
OUT_ROBUST = Path("data/universe/earnings_yield_robustness_p610.json")
OUT_QUAD = Path("data/universe/earnings_yield_quality_quadrants_p610.csv")
SNAPSHOT = "2026-11-05"
NEAR_ZERO = 0.001


def num(v):
    try:
        x = float(v); return x if math.isfinite(x) else None
    except (TypeError, ValueError): return None


def rank_series(values, higher=True):
    s = pd.Series(values, dtype=float)
    p = s.rank(pct=True, method="average") * 100
    if not higher: p = 100 - p
    return p.tolist()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rank", type=Path, default=RANK)
    ap.add_argument("--p68", type=Path, default=P68)
    ap.add_argument("--quality", type=Path, default=QUALITY)
    a = ap.parse_args()
    rrows = list(csv.DictReader(a.rank.open(encoding="utf-8")))
    target = [r for r in rrows if r["security_type"] in ("COMMON","ADR")]
    candidates = [r for r in target if r["candidate"] == "True"]
    ciks = {r["cik"] for r in candidates}
    qmap = {}
    equity_map = {}
    for r in csv.DictReader(a.p68.open(encoding="utf-8")):
        v = num(r.get("stockholders_equity"))
        if r.get("cik") and v is not None: equity_map[r["cik"]] = v
    if a.quality.exists():
        for r in csv.DictReader(a.quality.open(encoding="utf-8")):
            v = num(r.get("quality_v1_score"))
            if r.get("cik") and v is not None: qmap[r["cik"]] = v
    # issuer-level EY; same CIK shares value
    issuer = {}
    for r in candidates:
        cik = r["cik"]
        if cik and cik not in issuer:
            ey = num(r.get("earnings_yield"))
            invalid_period = bool(r.get("financial_period") and r["financial_period"] > SNAPSHOT)
            issuer[cik] = {"ey": None if invalid_period else ey, "raw_ey": ey,
                           "invalid_period": invalid_period,
                           "family": r["industry"], "accounting": r["accounting_standard"]}
    # peer groups for EY
    groups = defaultdict(list)
    for cik, x in issuer.items():
        if x["ey"] is not None: groups[(x["family"], x["accounting"])].append((cik, x["ey"]))
    ranks = {}
    group_meta = {}
    for key, vals in groups.items():
        if len(vals) < 30:
            group_meta[key] = {"valid_issuers": len(vals), "status": "INSUFFICIENT_PEER_GROUP",
                               "low": None, "high": None}
            for cik, v in vals:
                ranks[cik] = {"status": "INSUFFICIENT_PEER_GROUP", "pct": None, "pct_raw": None,
                              "winsor": None, "rank": None, "quintile": None, "raw": v}
            continue
        xs = [v for _, v in vals]
        lo, hi = np.percentile(xs, [1,99])
        clipped = [min(max(v, lo), hi) for v in xs]
        pct = rank_series(xs, True); wpct = rank_series(clipped, True)
        order = sorted(range(len(vals)), key=lambda i: xs[i], reverse=True)
        # average rank for ties
        for pos, idx in enumerate(order):
            vals[idx] = (vals[idx][0], vals[idx][1])
        # use percentile-derived quintile and rank
        for i, (cik, v) in enumerate(vals):
            q = min(5, max(1, int(np.ceil(wpct[i] / 20.0))))
            ranks[cik] = {"status": "RANK_AVAILABLE", "pct": wpct[i], "pct_raw": pct[i],
                          "winsor": clipped[i], "raw": v,
                          "rank": sum(1 for j in order if vals[j][1] > v) + 1, "quintile": q}
        group_meta[key] = {"valid_issuers": len(vals), "status": "RANK_AVAILABLE",
                           "low": float(lo), "high": float(hi)}
    # security rows
    scores = []
    for r in target:
        cik = r["cik"]; cand = r["candidate"] == "True"; x = ranks.get(cik) if cand else None
        ey = num(r.get("earnings_yield"))
        invalid_period = bool(r.get("financial_period") and r["financial_period"] > SNAPSHOT)
        status = "METRIC_BLOCKED"; reason = []
        if invalid_period: reason.append("FINANCIAL_PERIOD_AFTER_SNAPSHOT")
        if not cand:
            reason.append("NOT_P68_VALUE_DATA_READY")
        elif ey is None:
            status = "METRIC_BLOCKED"; reason.append("NET_INCOME_MISSING")
        elif invalid_period:
            status = "METRIC_BLOCKED"
        elif x and x["status"] == "RANK_AVAILABLE":
            status = "METRIC_RANK_AVAILABLE"
        elif x and x["status"] == "INSUFFICIENT_PEER_GROUP":
            status = "INSUFFICIENT_PEER_GROUP"; reason.append("INSUFFICIENT_PEER_GROUP")
        else:
            status = "METRIC_BLOCKED"
        if ey is not None and ey < 0: reason.append("NEGATIVE_EARNINGS_RETAINED")
        if ey is not None and abs(ey) < NEAR_ZERO: reason.append("NEAR_ZERO_EARNINGS")
        q = qmap.get(cik)
        quadrant = ""
        if ey is not None and q is not None:
            # global median split, explicitly cross-sectional diagnostic only
            quadrant = ("HIGH_EY_HIGH_Q" if ey >= 0 else "HIGH_EY_LOW_Q")
        scores.append({"ticker": r["ticker"], "cik": cik, "exchange": r["exchange"],
            "security_type": r["security_type"], "cohort": r["cohort"],
            "industry": r["industry"], "accounting_standard": r["accounting_standard"],
            "market_cap": r["market_cap"], "pe": r.get("pe"), "pb": r.get("pb"), "ps": r.get("ps"),
            "fcf_yield": r.get("fcf_yield"), "candidate": cand, "financial_period": r["financial_period"],
            "filed": r["filed"], "accn": r["accn"], "financial_period_invalid": invalid_period,
            "earnings_yield": ey if ey is not None else "",
            "earnings_yield_winsorized": x["winsor"] if x and x["status"]=="RANK_AVAILABLE" else "",
            "earnings_yield_percentile": x["pct"] if x and x["status"]=="RANK_AVAILABLE" else "",
            "earnings_yield_percentile_raw": x["pct_raw"] if x and x["status"]=="RANK_AVAILABLE" else "",
            "earnings_yield_rank": x["rank"] if x and x["status"]=="RANK_AVAILABLE" else "",
            "earnings_yield_quintile": x["quintile"] if x and x["status"]=="RANK_AVAILABLE" else "",
            "quality_v1_score": q if q is not None else "",
            "quality_quadrant": quadrant,
            "status": status, "blocker_codes": "|".join(dict.fromkeys(reason)),
            "research_label": "RESEARCH_ONLY_NOT_ALPHA_NOT_BACKTESTED"})
        # note quadrant computed below with medians
    # compute global medians among common EY/quality
    common = [(s["earnings_yield"], s["quality_v1_score"]) for s in scores
              if s["earnings_yield"] != "" and s["quality_v1_score"] != ""]
    med_ey = float(np.median([x[0] for x in common])) if common else None
    med_q = float(np.median([x[1] for x in common])) if common else None
    for s in scores:
        if s["earnings_yield"] != "" and s["quality_v1_score"] != "" and not s.get("financial_period_invalid") and med_ey is not None:
            e = s["earnings_yield"]; q = s["quality_v1_score"]
            s["quality_quadrant"] = ("HIGH_EY_HIGH_Q" if e >= med_ey and q >= med_q else
                                     "HIGH_EY_LOW_Q" if e >= med_ey else
                                     "LOW_EY_HIGH_Q" if q >= med_q else "LOW_EY_LOW_Q")
    OUT_SCORES.parent.mkdir(parents=True, exist_ok=True)
    with OUT_SCORES.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(scores[0].keys())); w.writeheader(); w.writerows(scores)
    # categories
    cand_scores = [s for s in scores if s["security_type"] in ("COMMON","ADR") and s["candidate"] == "True"] if False else \
                  [s for s in scores if s["cohort"] == "TARGET" and s["status"] != "METRIC_BLOCKED" or (s["cohort"]=="TARGET" and s["earnings_yield"]=="")]
    # use candidates by ticker set
    cand_set = {r["ticker"] for r in candidates}
    cs = [s for s in scores if s["ticker"] in cand_set]
    cats = {"POSITIVE_EARNINGS": [], "NEGATIVE_EARNINGS": [], "ZERO_OR_NEAR_ZERO_EARNINGS": [], "NET_INCOME_MISSING": [], "FINANCIAL_PERIOD_INVALID": []}
    for s in cs:
        ey = num(s["earnings_yield"])
        if s.get("financial_period_invalid"): cats["FINANCIAL_PERIOD_INVALID"].append(s)
        elif ey is None: cats["NET_INCOME_MISSING"].append(s)
        elif ey > 0 and abs(ey) >= NEAR_ZERO: cats["POSITIVE_EARNINGS"].append(s)
        elif ey < 0 and abs(ey) >= NEAR_ZERO: cats["NEGATIVE_EARNINGS"].append(s)
        else: cats["ZERO_OR_NEAR_ZERO_EARNINGS"].append(s)
    def dist(rs):
        vals = [float(s["earnings_yield"]) for s in rs if s["earnings_yield"] != ""]
        return {"n": len(rs), "min": min(vals) if vals else None, "median": float(np.median(vals)) if vals else None,
                "max": max(vals) if vals else None}
    coverage = {"metadata": {"generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_date": SNAPSHOT, "source": str(a.rank), "formula": "Net Income / verified issuer market cap",
        "pearson_note": "Pearson on raw; Spearman on ranks", "category": list(cats.keys())},
        "pool": {"target": len(target), "candidates": len(candidates), "unique_ciks": len(ciks),
                 "ey_valid": sum(1 for s in cs if s["earnings_yield"] != "" and not s.get("financial_period_invalid")),
                 "ey_ranked": sum(1 for s in cs if s["status"]=="METRIC_RANK_AVAILABLE")},
        "categories": {k: {"n": len(v), "distribution": dist(v)} for k,v in cats.items()},
        "by_type": {typ: {"candidates": sum(1 for s in cs if s["security_type"]==typ),
                          "valid": sum(1 for s in cs if s["security_type"]==typ and s["earnings_yield"]!="" and not s.get("financial_period_invalid"))}
                    for typ in ("COMMON","ADR")},
        "by_accounting": {acc: {"candidates": sum(1 for s in cs if s["accounting_standard"]==acc),
                                "valid": sum(1 for s in cs if s["accounting_standard"]==acc and s["earnings_yield"]!="" and not s.get("financial_period_invalid")),
                                "ranked": sum(1 for s in cs if s["accounting_standard"]==acc and s["status"]=="METRIC_RANK_AVAILABLE")}
                          for acc in sorted({s["accounting_standard"] for s in cs})},
        "by_family": {fam: {"candidates": sum(1 for s in cs if s["industry"]==fam),
                            "valid": sum(1 for s in cs if s["industry"]==fam and s["earnings_yield"]!="" and not s.get("financial_period_invalid"))}
                      for fam in sorted({s["industry"] for s in cs})},
        "peer_groups": {f"{k[0]}|{k[1]}": v for k,v in group_meta.items()},
        "quadrant_medians": {"earnings_yield": med_ey, "quality": med_q},
        "historical_gate": {"member_session_coverage": 0.795801, "ticker_coverage": 0.697772,
                            "backtest_ready": False, "validation_ready": False,
                            "inherits": "P6.7 gate failure; no forward return test run"}}
    OUT_COV.write_text(json.dumps(coverage, indent=2, ensure_ascii=False), encoding="utf-8")
    # quadrants
    qrows = []
    for q, rs in sorted((k, [s for s in scores if s["quality_quadrant"]==k]) for k in
                        ("HIGH_EY_HIGH_Q","HIGH_EY_LOW_Q","LOW_EY_HIGH_Q","LOW_EY_LOW_Q")):
        qrows.append({"quadrant": q, "n": len(rs), "avg_ey": float(np.mean([s["earnings_yield"] for s in rs])) if rs else None,
                      "avg_quality": float(np.mean([s["quality_v1_score"] for s in rs])) if rs else None,
                      "negative_equity": sum(1 for x in rs if equity_map.get(x["cik"], 0) < 0),
                      "note": "global median split; research diagnostic only"})
    with OUT_QUAD.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(qrows[0].keys())); w.writeheader(); w.writerows(qrows)
    # correlations on unique issuer common samples
    data = []
    for cik, x in issuer.items():
        r = next((s for s in cs if s["cik"] == cik), None)
        if not r: continue
        data.append({"cik": cik, "ey": x["ey"], "fcf": num(r.get("fcf_yield")),
                     "pb": num(r.get("pb")), "ps": num(r.get("ps")), "q": qmap.get(cik),
                     "accounting": r["accounting_standard"], "family": r["industry"]})
    df = pd.DataFrame(data)
    def corr_pair(a, b):
        z = df[[a,b]].dropna()
        return {"n": len(z), "pearson": float(z[a].corr(z[b], method="pearson")) if len(z)>2 else None,
                "spearman": float(z[a].corr(z[b], method="spearman")) if len(z)>2 else None}
    corr = {"pairs": {name: corr_pair(a,b) for name,a,b in (
                ("EY_FCF", "ey","fcf"),("EY_Quality","ey","q"),("EY_PB","ey","pb"),("EY_PS","ey","ps"))},
            "by_accounting": {}, "by_family": {},
            "pe_ey": {"n": sum(1 for s in cs if s["earnings_yield"]!="" and s["pe"]), "spearman": -1.0,
                      "note": "mathematical reciprocal for positive earnings"}}
    for acc in sorted(df["accounting"].dropna().unique()):
        z = df[df.accounting==acc]
        corr["by_accounting"][acc] = {"n": len(z), "EY_FCF": float(z[["ey","fcf"]].dropna().corr(method="spearman").iloc[0,1]) if len(z[["ey","fcf"]].dropna())>2 else None,
                                      "EY_Quality": float(z[["ey","q"]].dropna().corr(method="spearman").iloc[0,1]) if len(z[["ey","q"]].dropna())>2 else None}
    for fam in sorted(df["family"].dropna().unique()):
        z = df[df.family==fam]
        corr["by_family"][fam] = {"n": len(z), "EY_FCF": float(z[["ey","fcf"]].dropna().corr(method="spearman").iloc[0,1]) if len(z[["ey","fcf"]].dropna())>2 else None,
                                  "EY_Quality": float(z[["ey","q"]].dropna().corr(method="spearman").iloc[0,1]) if len(z[["ey","q"]].dropna())>2 else None}
    OUT_CORR.write_text(json.dumps(corr, indent=2, ensure_ascii=False), encoding="utf-8")
    # robustness: winsor vs raw; positive-only; groups; periods
    def rank_metric(rows, values_key, groups_allowed=None):
        out = {}
        for g, grp in pd.DataFrame(rows).groupby(["industry","accounting_standard"]):
            if groups_allowed and g not in groups_allowed: continue
            z = grp[[values_key,"cik"]].dropna()
            if len(z) < 30: continue
            for c, v in z.set_index("cik").itertuples(): out[c] = v
        return out
    paired = [(float(s["earnings_yield_percentile_raw"]), float(s["earnings_yield_percentile"])) for s in cs
              if s["earnings_yield_percentile"] != "" and s["earnings_yield_percentile_raw"] != ""]
    rb = {"winsorization": {"n": len(paired),
            "spearman": float(pd.Series([x[0] for x in paired]).corr(pd.Series([x[1] for x in paired]), method="spearman")) if paired else None,
            "mean_abs_percentile_change": float(np.mean([abs(x[0]-x[1]) for x in paired])) if paired else None,
            "p95_abs_percentile_change": float(np.percentile([abs(x[0]-x[1]) for x in paired],95)) if paired else None,
            "max_abs_percentile_change": float(max(abs(x[0]-x[1]) for x in paired)) if paired else None},
          "positive_vs_mixed": {"positive_n": len(cats["POSITIVE_EARNINGS"]), "negative_n": len(cats["NEGATIVE_EARNINGS"]),
                                "near_zero_n": len(cats["ZERO_OR_NEAR_ZERO_EARNINGS"]), "missing_n": len(cats["NET_INCOME_MISSING"])},
          "by_accounting": {acc: {"n": sum(1 for s in cs if s["accounting_standard"]==acc and s["earnings_yield"]!="" and not s.get("financial_period_invalid"))} for acc in sorted({s["accounting_standard"] for s in cs})},
          "by_family": {fam: {"n": sum(1 for s in cs if s["industry"]==fam and s["earnings_yield"]!="")} for fam in sorted({s["industry"] for s in cs})},
          "financial_periods": dict(Counter(s["financial_period"] for s in cs if s["earnings_yield"]!="").most_common()),
          "invalid_financial_period_records": sum(1 for s in cs if s.get("financial_period_invalid")),
          "historical_gate": {"member_session_coverage": 0.795801, "ticker_coverage": 0.697772,
                              "backtest_ready": False, "validation_ready": False,
                              "note": "P6.7 gate remains failed; no Q5-Q1/HAC/IC test run"},
          "formula_unchanged": True}
    OUT_ROBUST.write_text(json.dumps(rb, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"pool": coverage["pool"], "categories": {k:len(v) for k,v in cats.items()},
                      "quadrants": {r["quadrant"]:r["n"] for r in qrows},
                      "corr": corr["pairs"], "winsor": rb["winsorization"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
