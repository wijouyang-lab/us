"""P6.9 standalone cross-sectional study of five Value metrics.

Uses P6.8 readiness fields; no external requests. Rankings are issuer-level
within model_family × accounting_standard and are research-only.
"""
from __future__ import annotations
import argparse, csv, gzip, json, math
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

P68 = Path("data/universe/value_v1_readiness_p68.csv")
PANEL = Path("data/universe/sec_fundamentals_panel_p63.csv.gz")
OUT_RANK = Path("data/universe/value_metric_rankings_p69.csv")
OUT_COV = Path("data/universe/value_metric_coverage_p69.csv")
OUT_GROUPS = Path("data/universe/value_metric_peer_groups_p69.csv")
OUT_CORR = Path("data/universe/value_metric_correlations_p69.json")
OUT_AUDIT = Path("data/universe/value_metric_audit_p69.json")
SNAPSHOT = date(2026, 11, 5)
METRICS = ("pe","pb","ps","earnings_yield","fcf_yield")
FIELD = {"pe":"pe_derived","pb":"pb","ps":"ps","earnings_yield":"earnings_yield","fcf_yield":"fcf_yield"}
DIRECTION = {"pe": -1, "pb": -1, "ps": -1, "earnings_yield": 1, "fcf_yield": 1}
LABEL = {"pe":"PE","pb":"PB","ps":"PS","earnings_yield":"EarningsYield","fcf_yield":"FCFYield"}


def num(v):
    try:
        x = float(v); return x if math.isfinite(x) else None
    except (TypeError, ValueError): return None


def latest_pit(panel: Path):
    """Latest visible annual period metadata per CIK, for output provenance."""
    best = {}
    with gzip.open(panel, "rt", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            cik = (r.get("cik") or "").zfill(10)
            end = r.get("end") or ""
            filed = r.get("filed") or ""
            try:
                if date.fromisoformat(filed[:10]) > SNAPSHOT: continue
            except ValueError: pass
            if not filed: continue
            if cik not in best or (end, filed, r.get("accn") or "") > (best[cik]["financial_period"], best[cik]["filed"], best[cik]["accn"]):
                best[cik] = {"financial_period": end, "filed": filed, "accn": r.get("accn") or ""}
    return best


def percentile(values, higher_better=True):
    s = pd.Series(values, dtype=float)
    p = s.rank(pct=True, method="average") * 100.0
    return (p if higher_better else 100.0 - p).tolist()


def compute_group(vals, higher_better):
    """vals: list[(cik, value)]; returns cik->(raw_pct, winsor_pct, raw, clipped, low, high)."""
    xs = [v for _, v in vals]
    lo, hi = np.percentile(xs, [1, 99])
    clipped = [min(max(v, lo), hi) for v in xs]
    rawp = percentile(xs, higher_better)
    winp = percentile(clipped, higher_better)
    return {cik: {"raw_pct": rawp[i], "winsor_pct": winp[i], "raw": vals[i][1],
                  "winsorized": clipped[i], "low": float(lo), "high": float(hi)}
            for i, (cik, _) in enumerate(vals)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--p68", type=Path, default=P68)
    ap.add_argument("--panel", type=Path, default=PANEL)
    a = ap.parse_args()
    if not a.p68.exists(): print("P6.8 READINESS MISSING"); return 2
    rows = list(csv.DictReader(a.p68.open(encoding="utf-8")))
    target = [r for r in rows if r["security_type"] in ("COMMON","ADR")]
    candidates = [r for r in target if r["value_v1_status"] == "VALUE_V1_DATA_READY"]
    cand_ciks = {r["cik"] for r in candidates if r["cik"]}
    provenance = latest_pit(a.panel) if a.panel.exists() else {}
    # issuer-level values; first security per CIK; same CIK gets same ranking
    issuer = {}
    for r in candidates:
        cik = r["cik"]
        if not cik or cik in issuer: continue
        issuer[cik] = {"model_family": r["model_family"], "accounting_standard": r["accounting_standard"],
                       "values": {m: num(r.get(FIELD[m])) for m in METRICS}}
    # group ranks
    metrics_result = {}; group_rows = []
    for m in METRICS:
        groups = defaultdict(list)
        for cik, x in issuer.items():
            v = x["values"][m]
            if v is not None:
                groups[(x["model_family"], x["accounting_standard"])].append((cik, v))
        ranked = {}; groups_meta = {}
        for key, vals in groups.items():
            if len(vals) < 30:
                groups_meta[key] = {"valid_issuers": len(vals), "status": "INSUFFICIENT_PEER_GROUP",
                                    "low": None, "high": None, "ranked": 0}
                for cik, v in vals:
                    ranked[cik] = {"raw_pct": None, "winsor_pct": None, "raw": v, "winsorized": None,
                                   "low": None, "high": None, "status": "INSUFFICIENT_PEER_GROUP"}
            else:
                g = compute_group(vals, DIRECTION[m] > 0)
                for cik, x in g.items():
                    x["status"] = "RANK_AVAILABLE"; ranked[cik] = x
                groups_meta[key] = {"valid_issuers": len(vals), "status": "RANK_AVAILABLE",
                                    "low": g[vals[0][0]]["low"], "high": g[vals[0][0]]["high"],
                                    "ranked": len(vals)}
            group_rows.append({"metric": m, "model_family": key[0], "accounting_standard": key[1],
                               "valid_issuers": groups_meta[key]["valid_issuers"],
                               "status": groups_meta[key]["status"], "winsor_low": groups_meta[key]["low"],
                               "winsor_high": groups_meta[key]["high"], "ranked_issuers": groups_meta[key]["ranked"]})
        metrics_result[m] = ranked
    # security rows
    out = []
    for r in rows:
        cik = r["cik"]; cand = r["value_v1_status"] == "VALUE_V1_DATA_READY"
        rec = {"ticker": r["ticker"], "cik": cik, "exchange": r["exchange"],
               "security_type": r["security_type"], "cohort": r["cohort"],
               "industry": r["model_family"], "accounting_standard": r["accounting_standard"],
               "market_cap": r["market_cap_raw"], "candidate": cand,
               "financial_period": provenance.get(cik, {}).get("financial_period", ""),
               "filed": provenance.get(cik, {}).get("filed", ""), "accn": provenance.get(cik, {}).get("accn", "")}
        statuses = []
        for m in METRICS:
            rec[m] = r.get(FIELD[m], "")
            if not cand:
                rec[m + "_status"] = "METRIC_BLOCKED"; rec[m + "_percentile"] = ""
                rec[m + "_percentile_raw"] = ""; rec[m + "_winsorized"] = ""
            else:
                x = metrics_result[m].get(cik)
                if x is None:
                    rec[m + "_status"] = "METRIC_BLOCKED"; rec[m + "_percentile"] = ""
                    rec[m + "_percentile_raw"] = ""; rec[m + "_winsorized"] = ""
                else:
                    rec[m + "_status"] = x["status"]; rec[m + "_percentile"] = x["winsor_pct"] if x["winsor_pct"] is not None else ""
                    rec[m + "_percentile_raw"] = x["raw_pct"] if x["raw_pct"] is not None else ""
                    rec[m + "_winsorized"] = x["winsorized"] if x["winsorized"] is not None else ""
            statuses.append(rec[m + "_status"])
        if not cand:
            overall = "METRIC_BLOCKED"
        elif any(s == "RANK_AVAILABLE" for s in statuses):
            overall = "METRIC_RANK_AVAILABLE"
        elif any(s == "INSUFFICIENT_PEER_GROUP" for s in statuses):
            overall = "INSUFFICIENT_PEER_GROUP"
        elif any(s == "METRIC_DATA_READY" for s in statuses):
            overall = "METRIC_DATA_READY"
        else:
            overall = "METRIC_BLOCKED"
        rec["scoring_status"] = overall
        blockers = []
        if not cand: blockers.append("NOT_P68_VALUE_DATA_READY")
        for m in METRICS:
            if rec[m + "_status"] == "INSUFFICIENT_PEER_GROUP": blockers.append(m.upper() + "_INSUFFICIENT_PEER_GROUP")
            if rec[m + "_status"] == "METRIC_BLOCKED": blockers.append(m.upper() + "_BLOCKED")
        rec["blocker_codes"] = "|".join(dict.fromkeys(blockers))
        out.append(rec)
    OUT_RANK.parent.mkdir(parents=True, exist_ok=True)
    with OUT_RANK.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    # coverage by candidate securities and unique CIK
    cov = []
    for m in METRICS:
        valid_rows = [r for r in candidates if num(r.get(FIELD[m])) is not None]
        valid_ciks = {r["cik"] for r in valid_rows}
        ranked_ciks = {c for c, x in metrics_result[m].items() if x["status"] == "RANK_AVAILABLE"}
        cov.append({"metric": LABEL[m], "candidate_securities": len(candidates),
                    "candidate_unique_ciks": len(cand_ciks),
                    "valid_securities": len(valid_rows), "valid_unique_ciks": len(valid_ciks),
                    "coverage_securities": round(len(valid_rows)/len(candidates),6) if candidates else 0,
                    "coverage_ciks": round(len(valid_ciks)/len(cand_ciks),6) if cand_ciks else 0,
                    "ranked_unique_ciks": len(ranked_ciks)})
    with OUT_COV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(cov[0].keys())); w.writeheader(); w.writerows(cov)
    with OUT_GROUPS.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(group_rows[0].keys())); w.writeheader(); w.writerows(group_rows)
    # correlations on unique candidate issuers
    data = pd.DataFrame([{"cik": cik, **{m: x["values"][m] for m in METRICS}} for cik, x in issuer.items()]).set_index("cik")
    corr = data.corr(method="spearman").round(6).to_dict()
    pe_ey = data[["pe","earnings_yield"]].dropna()
    pe_ey_corr = float(pe_ey["pe"].corr(pe_ey["earnings_yield"], method="spearman")) if len(pe_ey) > 2 else None
    # winsor rank impact
    diffs = []
    for m in METRICS:
        for cik, x in metrics_result[m].items():
            if x["raw_pct"] is not None and x["winsor_pct"] is not None:
                diffs.append(abs(float(x["raw_pct"]) - float(x["winsor_pct"])))
    # intersections
    sets = {m: {cik for cik, x in issuer.items() if x["values"][m] is not None} for m in METRICS}
    intersection = set.intersection(*sets.values()) if sets else set()
    by_type = {}; by_acc = {}; by_family = {}
    for typ in ("COMMON","ADR"):
        rs = [r for r in candidates if r["security_type"] == typ]
        by_type[typ] = {"securities": len(rs), **{LABEL[m]: sum(1 for r in rs if num(r.get(FIELD[m])) is not None) for m in METRICS}}
    for acc in sorted({r["accounting_standard"] for r in candidates}):
        rs = [r for r in candidates if r["accounting_standard"] == acc]
        by_acc[acc] = {"securities": len(rs), **{LABEL[m]: sum(1 for r in rs if num(r.get(FIELD[m])) is not None) for m in METRICS}}
    for fam in sorted({r["model_family"] for r in candidates}):
        rs = [r for r in candidates if r["model_family"] == fam]
        by_family[fam] = {"securities": len(rs), **{LABEL[m]: sum(1 for r in rs if num(r.get(FIELD[m])) is not None) for m in METRICS}}
    extremes = {}
    for m in METRICS:
        vals = [x["values"][m] for x in issuer.values() if x["values"][m] is not None]
        if vals:
            q1, q99 = np.percentile(vals, [1,99])
            extremes[LABEL[m]] = {"n": len(vals), "min": float(min(vals)), "max": float(max(vals)),
                                  "q01": float(q1), "q99": float(q99),
                                  "outside_winsor": int(sum(1 for v in vals if v < q1 or v > q99))}
    audit = {"metadata": {"generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_date": str(SNAPSHOT), "p68_file": str(a.p68),
        "ranking_unit": "unique CIK within model_family x accounting_standard",
        "min_peer_issuers": 30, "winsorization": "1%/99% within metric peer group",
        "research_label": "RESEARCH_ONLY_NOT_ALPHA_NOT_BACKTESTED"},
        "pool": {"target_securities": len(target), "candidate_securities": len(candidates),
                 "candidate_unique_ciks": len(cand_ciks), "issuer_rows": len(issuer)},
        "coverage": cov,
        "intersections": {"all_five": len(intersection),
                          "four_of_five": sum(1 for cik in cand_ciks if sum(1 for m in METRICS if cik in sets[m]) == 4),
                          "three_of_five": sum(1 for cik in cand_ciks if sum(1 for m in METRICS if cik in sets[m]) == 3)},
        "by_type": by_type, "by_accounting": by_acc, "by_family": by_family,
        "correlations": corr, "pe_earnings_yield_spearman": pe_ey_corr,
        "pe_ey_positive_overlap": len(pe_ey),
        "winsorization_rank_abs_change": {"n": len(diffs), "mean": round(float(np.mean(diffs)),4) if diffs else None,
                                          "p95": round(float(np.percentile(diffs,95)),4) if diffs else None,
                                          "max": round(float(max(diffs)),4) if diffs else None},
        "extremes": extremes,
        "provider_pe_mismatch_gt_20": sum(1 for r in candidates if num(r.get("pe_mismatch")) is not None and num(r.get("pe_mismatch")) > 0.2),
        "duplicate_cik_candidate_securities": len(candidates) - len(cand_ciks),
        "negative_earnings": sum(1 for r in candidates if num(r.get("net_income")) is not None and num(r.get("net_income")) < 0),
        "negative_equity": sum(1 for r in candidates if num(r.get("stockholders_equity")) is not None and num(r.get("stockholders_equity")) <= 0),
        "negative_fcf": sum(1 for r in candidates if num(r.get("free_cash_flow")) is not None and num(r.get("free_cash_flow")) < 0),
        "different_financial_periods": len({p["financial_period"] for p in provenance.values() if p["financial_period"]}),
        "status_counts": dict(Counter(r["scoring_status"] for r in out if r["security_type"] in ("COMMON","ADR"))),
        "metric_groups": len(group_rows),
        "notes": ["No composite score or weights are produced.",
                  "PE and Earnings Yield are mathematically reciprocal for positive earnings.",
                  "SIC model family is not GICS."]}
    a_corr = {"pe_earnings_yield_spearman": pe_ey_corr, "pearson_pe_ey": None,
              "spearman_matrix": corr, "note": "PE/EY are reciprocal for positive earnings; not independent factors."}
    OUT_CORR.write_text(json.dumps(a_corr, indent=2, ensure_ascii=False), encoding="utf-8")
    OUT_AUDIT.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"pool": audit["pool"], "coverage": cov, "intersections": audit["intersections"],
                      "pe_ey_spearman": pe_ey_corr, "status": audit["status_counts"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
