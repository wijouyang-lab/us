"""P6.14 reproducible fundamental selection engine.

Value V1: four independent valuation metrics ranked inside SIC model family x
accounting standard. A composite is explicitly EXPERIMENTAL equal-weight and is
never a formal strategy.
Quality V1: reuses the P6.6 scored rows, validates their weighted formula and
emits issuer-level rankings.
GARP: historical growth only; no forward EPS, PEG or forecast.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

AS_OF = date(2026, 11, 5)
VALUE_INPUT = Path("data/universe/selection_inputs/value_metric_rankings_p69.csv")
QUALITY_INPUT = Path("data/universe/selection_inputs/quality_v1_scores_p66.csv")
IDENTITY_INPUT = Path("data/universe/selection_inputs/us_equities_current.csv")
SIC_INPUT = Path("data/universe/selection_inputs/sec_sic_model_family_map_p65.csv")
GARP_INPUT = Path("data/universe/selection_inputs/garp_growth_metrics_p614.csv")
OUT = Path("data/universe/selection")
VALUE_METRICS = ("pb", "ps", "earnings_yield", "fcf_yield")
GARP_METRICS = ("revenue_growth_1y", "revenue_cagr_3y", "eps_growth_1y",
                "fcf_growth_1y", "earnings_stability",
                "operating_margin_expansion", "operating_leverage")
MIN_PEER = 30
QUALITY_W = {"roe": .30, "roa": .25, "cfo": .25, "leverage": .20}


def read_csv(path: Path):
    b = path.read_bytes()[:2]
    enc = "utf-16" if b in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    with path.open(encoding=enc, newline="") as f:
        return list(csv.DictReader(f))


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def sha(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pct(values, higher=True):
    if not values: return []
    s = pd.Series(values, dtype=float).rank(pct=True, method="average") * 100.0
    vals = s.tolist()
    return vals if higher else [100.0 - x for x in vals]


def winsor_pct(items, higher=True):
    """items list[(key,value)] in one peer group -> key -> (raw_pct, winsor_pct, raw, clip, lo, hi)."""
    if len(items) < MIN_PEER: return {}, None
    vals = [x[1] for x in items]
    lo, hi = np.percentile(vals, [1, 99])
    clipped = [min(max(x, lo), hi) for x in vals]
    raw = pct(vals, higher); win = pct(clipped, higher)
    return {k: {"raw_pct": raw[i], "winsor_pct": win[i], "raw": vals[i],
                "winsorized": clipped[i], "low": float(lo), "high": float(hi)}
            for i, (k, _) in enumerate(items)}, (float(lo), float(hi))


def identity_map(rows):
    by_cik = defaultdict(list); by_ticker = {}
    for r in rows:
        cik = (r.get("CIK") or "").zfill(10)
        if cik and r.get("security_type") in ("COMMON", "ADR"):
            by_cik[cik].append(r)
        by_ticker[r.get("ticker", "")] = r
    out = {}
    for cik, rs in by_cik.items():
        rs.sort(key=lambda x: (x.get("security_type") != "COMMON", x.get("ticker", "")))
        x = rs[0]; out[cik] = {"company_name": x.get("security_name", ""),
                               "ticker": x.get("ticker", ""), "security_type": x.get("security_type", "")}
    return out, by_ticker


def value_build(value_rows, identity):
    # one issuer per CIK; candidate only for ranking
    by_cik = {}
    for r in value_rows:
        cik = (r.get("cik") or "").zfill(10)
        if not cik or r.get("security_type") not in ("COMMON", "ADR"): continue
        if cik not in by_cik or (r.get("candidate") == "True" and by_cik[cik].get("candidate") != "True"):
            by_cik[cik] = r
    rows = []; metrics = {}
    for cik, r in by_cik.items():
        cand = r.get("candidate") == "True"
        rec = {"ticker": r.get("ticker", ""), "cik": cik,
               "company_name": identity.get(cik, {}).get("company_name", ""),
               "security_type": r.get("security_type", ""),
               "model_family": r.get("industry") or "UNCLASSIFIED",
               "accounting_standard": r.get("accounting_standard") or "NONE",
               "market_cap": r.get("market_cap", ""), "financial_period": r.get("financial_period", ""),
               "filed": r.get("filed", ""), "accn": r.get("accn", ""),
               "source_url": (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{(r.get('accn') or '').replace('-', '')}/"
                              if r.get("accn") else ""),
               "candidate": cand, "data_as_of": AS_OF.isoformat()}
        if not cand:
            rec.update({"value_status": "VALUE_DATA_BLOCKED", "value_reason": "NOT_P6_8_VALUE_V1_READY",
                        "value_composite_experimental": "", "value_metric_count": 0, "value_selected_top50": False})
        elif r.get("filed") and r["filed"] > AS_OF.isoformat():
            rec.update({"value_status": "VALUE_PIT_BLOCKED", "value_reason": "FILED_AFTER_AS_OF",
                        "value_composite_experimental": "", "value_metric_count": 0, "value_selected_top50": False})
        else:
            rec.update({"value_status": "VALUE_PARTIAL", "value_reason": "", "value_composite_experimental": "",
                        "value_metric_count": 0, "value_selected_top50": False})
        for m in VALUE_METRICS:
            raw = num(r.get(m)); status = "RANK_AVAILABLE"
            if not cand: status = "BLOCKED"
            elif raw is None: status = "MISSING"
            elif m in ("pb", "ps") and raw <= 0: status = "NON_POSITIVE_NOT_CHEAP"
            elif r.get("filed") and r["filed"] > AS_OF.isoformat(): status = "PIT_BLOCKED"
            elif raw < 0: status = "NEGATIVE_VALUE_NOT_CHEAP"
            rec[m] = raw if raw is not None else ""
            rec[m + "_status"] = status
            rec[m + "_percentile"] = ""
            rec[m + "_winsorized"] = ""
        rows.append(rec); metrics[cik] = r
    # rank each metric within model_family x accounting
    for m in VALUE_METRICS:
        groups = defaultdict(list)
        for rec in rows:
            if rec[m + "_status"] not in ("RANK_AVAILABLE", "NEGATIVE_VALUE_NOT_CHEAP"): continue
            groups[(rec["model_family"], rec["accounting_standard"])].append((rec["cik"], rec[m]))
        for key, items in groups.items():
            ranked, _ = winsor_pct(items, higher=(m in ("earnings_yield", "fcf_yield")))
            for cik, x in ranked.items():
                rec = next(r for r in rows if r["cik"] == cik)
                rec[m + "_percentile"] = round(x["winsor_pct"], 6)
                rec[m + "_winsorized"] = x["winsorized"]
                if rec[m + "_status"] == "NEGATIVE_VALUE_NOT_CHEAP":
                    rec[m + "_status_ranked"] = "NEGATIVE_PERCENTILE_LOW"
    for rec in rows:
        vals = [rec[m + "_percentile"] for m in VALUE_METRICS]
        if (rec["value_status"] == "VALUE_PARTIAL" and all(v != "" for v in vals)
                and all(rec[m + "_status"] != "NEGATIVE_VALUE_NOT_CHEAP" for m in VALUE_METRICS)):
            rec["value_metric_count"] = 4
            rec["value_composite_experimental"] = round(sum(float(v) for v in vals) / 4.0, 6)
            rec["value_status"] = "VALUE_EXPERIMENTAL_ALL_FOUR"
            rec["value_reason"] = "EQUAL_WEIGHT_4_FACTOR_EXPERIMENTAL"
        elif rec["value_status"] == "VALUE_PARTIAL":
            rec["value_metric_count"] = sum(1 for v in vals if v != "")
            negative = [m for m in VALUE_METRICS if rec[m + "_status"] == "NEGATIVE_VALUE_NOT_CHEAP"]
            rec["value_reason"] = ("NEGATIVE_EARNINGS_OR_FCF_NOT_CHEAP:" + "|".join(negative)
                                   if negative else "MISSING_ONE_OR_MORE_VALUE_METRICS")
    ranked = sorted([r for r in rows if r["value_composite_experimental"] != ""],
                    key=lambda r: (-float(r["value_composite_experimental"]), r["ticker"], r["cik"]))
    for i, r in enumerate(ranked, 1):
        r["value_rank"] = i; r["value_selected_top50"] = i <= 50
    return rows, ranked


def quality_build(qrows, identity):
    by_cik = {}
    for r in qrows:
        cik = (r.get("cik") or "").zfill(10)
        if not cik: continue
        if cik not in by_cik or (r.get("scoring_status") == "QUALITY_V1_SCORED" and
                                 by_cik[cik].get("scoring_status") != "QUALITY_V1_SCORED"):
            by_cik[cik] = r
    rows = []; mismatches = 0
    for cik, r in by_cik.items():
        status = r.get("scoring_status", "QUALITY_V1_BLOCKED")
        rec = {"ticker": r.get("ticker", ""), "cik": cik,
               "company_name": identity.get(cik, {}).get("company_name", ""),
               "security_type": r.get("security_type", ""), "model_family": r.get("model_family") or r.get("industry") or "UNCLASSIFIED",
               "accounting_standard": r.get("accounting_standard") or "NONE",
               "financial_period": r.get("financial_period", ""), "filed": r.get("filed", ""),
               "accn": r.get("accn", ""), "data_as_of": r.get("data_as_of") or AS_OF.isoformat(),
               "roe": r.get("roe", ""), "roa": r.get("roa", ""),
               "cfo_to_avg_assets": r.get("cfo_to_avg_assets", ""), "liabilities_to_assets": r.get("liabilities_to_assets", ""),
               "roe_percentile": r.get("roe_percentile", ""), "roa_percentile": r.get("roa_percentile", ""),
               "cfo_percentile": r.get("cfo_percentile", ""), "leverage_percentile": r.get("leverage_percentile", ""),
               "quality_score_published": r.get("quality_v1_score", ""),
               "quality_rank_published": r.get("quality_v1_rank", ""),
               "quality_status": status, "quality_reason": r.get("blocker_codes", ""),
               "quality_score_recomputed": "", "quality_selected_top50": False}
        if status == "QUALITY_V1_SCORED":
            try:
                vals = {k: float(r.get(k + "_percentile")) for k in QUALITY_W}
                score = sum(vals[k] * w for k, w in QUALITY_W.items())
                rec["quality_score_recomputed"] = round(score, 6)
                pub = num(r.get("quality_v1_score"))
                if pub is None or abs(pub - score) > 0.02:
                    rec["quality_status"] = "QUALITY_SCORE_MISMATCH"; mismatches += 1
                    rec["quality_reason"] = "RECOMPUTED_WEIGHTED_SCORE_MISMATCH"
            except (TypeError, ValueError):
                rec["quality_status"] = "QUALITY_SCORE_MISMATCH"; mismatches += 1
                rec["quality_reason"] = "PERCENTILE_INPUT_MISSING"
        rows.append(rec)
    ranked = sorted([r for r in rows if r["quality_status"] == "QUALITY_V1_SCORED"],
                    key=lambda r: (-float(r["quality_score_recomputed"]), r["ticker"], r["cik"]))
    for i, r in enumerate(ranked, 1):
        r["quality_rank"] = i; r["quality_selected_top50"] = i <= 50
    return rows, ranked, mismatches


def garp_build(grows, quality_by_cik, identity):
    rows = []
    for r in grows:
        cik = (r.get("cik") or "").zfill(10)
        q = quality_by_cik.get(cik, {})
        rec = {"ticker": r.get("ticker", ""), "cik": cik,
               "company_name": identity.get(cik, {}).get("company_name") or r.get("company_name", ""),
               "security_type": r.get("security_type", ""),
               "model_family": q.get("model_family", "UNCLASSIFIED"),
               "accounting_standard": q.get("accounting_standard", "NONE"),
               "latest_period": r.get("latest_period", ""), "filed": r.get("filed", ""),
               "accn": r.get("accn", ""), "history_years": r.get("history_years", ""),
               "garp_status": r.get("status", "GARP_DATA_BLOCKED"),
               "garp_reason": r.get("reason_codes", ""), "garp_score": "",
               "garp_metric_count": r.get("history_metric_count", 0), "garp_selected_top50": False}
        for m in GARP_METRICS: rec[m] = r.get(m, "")
        rows.append(rec)
    for m in GARP_METRICS:
        groups = defaultdict(list)
        for r in rows:
            if r["garp_status"] != "GARP_HISTORY_AVAILABLE": continue
            v = num(r.get(m))
            if v is not None:
                groups[(r["model_family"], r["accounting_standard"])].append((r["cik"], v))
        for key, items in groups.items():
            ranked, _ = winsor_pct(items, higher=True)
            for cik, x in ranked.items():
                rec = next(r for r in rows if r["cik"] == cik)
                rec[m + "_percentile"] = round(x["winsor_pct"], 6)
    for r in rows:
        if r["garp_status"] != "GARP_HISTORY_AVAILABLE":
            continue
        vals = [r.get(m + "_percentile") for m in GARP_METRICS if r.get(m + "_percentile") not in (None, "")]
        if len(vals) >= 3:
            r["garp_score"] = round(sum(float(v) for v in vals) / len(vals), 6)
            r["garp_status"] = "GARP_EXPERIMENTAL_HISTORICAL_GROWTH"
            r["garp_reason"] = "EQUAL_WEIGHT_AVAILABLE_HISTORICAL_METRICS"
    ranked = sorted([r for r in rows if r["garp_score"] != ""],
                    key=lambda r: (-float(r["garp_score"]), r["ticker"], r["cik"]))
    for i, r in enumerate(ranked, 1):
        r["garp_rank"] = i; r["garp_selected_top50"] = i <= 50
    return rows, ranked


def write_csv(path: Path, rows, fields):
    fields = list(dict.fromkeys([k for row in rows for k in row.keys()] + list(fields)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--value", type=Path, default=VALUE_INPUT)
    ap.add_argument("--quality", type=Path, default=QUALITY_INPUT)
    ap.add_argument("--identity", type=Path, default=IDENTITY_INPUT)
    ap.add_argument("--garp", type=Path, default=GARP_INPUT)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    missing = [str(p) for p in (a.value, a.quality, a.identity, a.garp) if not p.exists()]
    if missing:
        print(json.dumps({"status": "DATA_BLOCKED", "missing": missing})); return 2
    identity_rows = read_csv(a.identity)
    identity, by_ticker = identity_map(identity_rows)
    value_source_rows = read_csv(a.value)
    all_five_intersection = sum(
        1 for r in value_source_rows
        if r.get("candidate") == "True" and r.get("security_type") == "COMMON"
        and all(r.get(f) not in ("", None) for f in ("pe", "pb", "ps", "earnings_yield", "fcf_yield")))

    vrows, vtop = value_build(read_csv(a.value), identity)
    qrows, qtop, qmis = quality_build(read_csv(a.quality), identity)
    grows = read_csv(a.garp)
    qby = {r["cik"]: r for r in qrows}
    gr, gtop = garp_build(grows, qby, identity)
    all_out = a.out; all_out.mkdir(parents=True, exist_ok=True)
    vf = list(vrows[0].keys()) if vrows else []
    qf = list(qrows[0].keys()) if qrows else []
    gf = list(gr[0].keys()) if gr else []
    write_csv(all_out / "value_rankings.csv", vrows, vf)
    write_csv(all_out / "quality_rankings.csv", qrows, qf)
    write_csv(all_out / "garp_rankings.csv", gr, gf)
    write_csv(all_out / "value_top50.csv", vtop[:50], vf)
    write_csv(all_out / "quality_top50.csv", qtop[:50], qf)
    write_csv(all_out / "garp_top50.csv", gtop[:50], gf)
    def brief(r, kind):
        base = {"ticker": r.get("ticker"), "cik": r.get("cik"), "company_name": r.get("company_name"),
                "model_family": r.get("model_family"), "accounting_standard": r.get("accounting_standard"),
                "status": r.get(kind + "_status"), "reason": r.get(kind + "_reason"),
                "financial_period": r.get("financial_period") or r.get("latest_period", ""),
                "filed": r.get("filed", ""), "accn": r.get("accn", ""),
                "data_as_of": AS_OF.isoformat(),
                "source_url": (f"https://www.sec.gov/Archives/edgar/data/{int(r['cik'])}/{(r.get('accn') or '').replace('-', '')}/"
                               if r.get("cik") and r.get("accn") else "")}
        if kind == "value":
            base.update({"score": r.get("value_composite_experimental"), "metrics": {m: r.get(m) for m in VALUE_METRICS},
                         "percentiles": {m: r.get(m + "_percentile") for m in VALUE_METRICS},
                         "missing_fields": [m for m in VALUE_METRICS if r.get(m) in ("", None)],
                         "market_cap": r.get("market_cap", ""),
                         "valuation_support": "P6.8_VALIDATED_MARKET_CAP"})
        elif kind == "quality":
            qfields = {"roe": "roe", "roa": "roa", "cfo": "cfo_to_avg_assets", "leverage": "liabilities_to_assets"}
            base.update({"score": r.get("quality_score_recomputed"), "metrics": {k: r.get(qfields[k]) for k in QUALITY_W},
                         "percentiles": {k: r.get(k + "_percentile") for k in QUALITY_W},
                         "missing_fields": [k for k, f in qfields.items() if r.get(f) in ("", None)],
                         "valuation_support": "NO_PRICE_DCF_NOT_VALIDATED"})
        else:
            base.update({"score": r.get("garp_score"), "metrics": {m: r.get(m) for m in GARP_METRICS},
                         "percentiles": {m: r.get(m + "_percentile") for m in GARP_METRICS},
                         "missing_fields": [m for m in GARP_METRICS if r.get(m) in ("", None)],
                         "valuation_support": "HISTORICAL_GROWTH_ONLY_NO_VALUATION"})
        return base
    def ids(rows): return {r["cik"] for r in rows}
    vt, qt, gt = ids(vtop[:50]), ids(qtop[:50]), ids(gtop[:50])
    snap = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "data_as_of": AS_OF.isoformat(),
        "status": "CURRENT_CROSS_SECTIONAL_RESEARCH",
        "pit_status": "PIT_BACKTEST_BLOCKED",
        "data_quality_status": "PARTIAL",
        "research_label": "RESEARCH_ONLY_NOT_A_BUY_SELL_SIGNAL",
        "inputs": {p.name: {"path": str(p), "sha256": sha(p), "rows": (len(vrows) if p == a.value else len(qrows) if p == a.quality else len(gr) if p == a.garp else len(identity_rows))} for p in (a.value, a.quality, a.identity, a.garp)},
        "value": {"candidate_issuers": sum(1 for r in vrows if r.get("candidate")),
                  "all_four_ranked": len(vtop), "all_five_p69_intersection": all_five_intersection,
                  "top50": [brief(r, "value") for r in vtop[:50]],
                  "formula": "equal-weight experimental average of winsorized within-peer percentiles: PB (inverse), PS (inverse), Earnings Yield (higher), FCF Yield (higher)"},
        "quality": {"scored_issuers": len(qtop), "score_mismatches": qmis,
                    "top50": [brief(r, "quality") for r in qtop[:50]],
                    "formula": "0.30 ROE + 0.25 ROA + 0.25 CFO/assets + 0.20 inverse liabilities/assets; P6.6 peer percentiles"},
        "garp": {"history_available": sum(1 for r in gr if r["garp_status"] in ("GARP_EXPERIMENTAL_HISTORICAL_GROWTH", "GARP_HISTORY_AVAILABLE")),
                 "ranked_issuers": sum(1 for r in gr if r["garp_status"] == "GARP_EXPERIMENTAL_HISTORICAL_GROWTH"),
                 "top50": [brief(r, "garp") for r in gtop[:50]],
                 "formula": "equal-weight available historical growth percentiles; no forward EPS/PEG"},
        "intersections": {"value_quality": len(vt & qt), "value_garp": len(vt & gt), "quality_garp": len(qt & gt),
                          "all_three": len(vt & qt & gt)},
    }
    (all_out / "selection_snapshot.json").write_text(json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")
    # data quality report
    vcov = {m: sum(1 for r in vrows if r.get(m + "_percentile") not in ("", None)) for m in VALUE_METRICS}
    qcov = {k: sum(1 for r in qrows if r.get(k + "_percentile") not in ("", None)) for k in QUALITY_W}
    gcov = {m: sum(1 for r in gr if r.get(m + "_percentile") not in ("", None)) for m in GARP_METRICS}
    dq = {"generated_at": snap["generated_at"], "data_as_of": AS_OF.isoformat(),
          "value": {"rows": len(vrows), "candidates": sum(1 for r in vrows if r.get("candidate")),
                    "all_four": len(vtop), "all_five_p69": all_five_intersection, "coverage": vcov,
                    "status_counts": dict(Counter(r["value_status"] for r in vrows))},
          "quality": {"rows": len(qrows), "scored": len(qtop), "coverage": qcov,
                      "score_mismatches": qmis, "status_counts": dict(Counter(r["quality_status"] for r in qrows))},
          "garp": {"rows": len(gr), "ranked": len(gtop), "coverage": gcov,
                   "status_counts": dict(Counter(r["garp_status"] for r in gr))},
          "limitations": ["CURRENT_CROSS_SECTIONAL_RESEARCH only; PIT_BACKTEST_BLOCKED.",
                          "Value composite is experimental equal-weight; no approved weights.",
                          "Quality peer percentiles are P6.6 current-sectional; no historical backtest.",
                          "GARP is historical growth only; no forward EPS, PEG or forecast.",
                          "Prices/market caps are P6.8-validated inputs; no new vendor quotes.",
                          "ADR and unclassified securities are excluded from Value/Quality standard rankings.",
                          "No production scan/review/evolve or PAPER-50000 state changed."]}
    (all_out / "selection_data_quality.json").write_text(json.dumps(dq, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"value_candidates": len(vrows), "value_all_four": len(vtop), "quality_scored": len(qtop),
                      "garp_ranked": len(gtop), "quality_mismatches": qmis, "out": str(all_out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
