"""P6.15 true peer/global sensitivity from raw metric values.

No scheme below reuses an already-grouped percentile as a "global" percentile.
All global and alternate-winsor schemes recompute from raw values.
"""
from __future__ import annotations
import csv, json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("data/universe/selection")
OUT = ROOT / "selection_sensitivity.json"
VM = ("pb", "ps", "earnings_yield", "fcf_yield")
QM = ("roe", "roa", "cfo", "leverage")
GM = ("revenue_growth_1y", "revenue_cagr_3y", "revenue_cagr_5y", "eps_growth_1y",
      "fcf_growth_1y", "earnings_stability", "operating_margin_expansion", "operating_leverage_ratio")


def load(name):
    with (ROOT / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def val(r, k):
    try:
        x = float(r.get(k))
        return x if np.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def rank(vals, higher=True, winsor=(1, 99)):
    if not vals: return {}
    keys = list(vals)
    xs = np.array([vals[k] for k in keys], dtype=float)
    if winsor != (0, 100):
        lo, hi = np.percentile(xs, winsor)
        xs = np.clip(xs, lo, hi)
    p = pd.Series(xs).rank(pct=True, method="average").to_numpy() * 100.0
    if not higher: p = 100.0 - p
    return {k: float(p[i]) for i, k in enumerate(keys)}


def top(score, n=50):
    return {k for k, v in sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))[:n]}


def value_global(rows, winsor=(1, 99)):
    cols = {}
    for m in VM:
        vals = {r["cik"]: val(r, m) for r in rows if val(r, m) is not None and val(r, m) > 0}
        cols[m] = rank(vals, higher=(m in ("earnings_yield", "fcf_yield")), winsor=winsor)
    common = set.intersection(*(set(x) for x in cols.values()))
    return {c: sum(cols[m][c] for m in VM) / 4 for c in common}


def main():
    v = [r for r in load("value_rankings.csv") if val(r, "value_composite_experimental") is not None]
    vtop = top({r["cik"]: val(r, "value_composite_experimental") for r in v})
    report = {"generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
              "data_as_of": "2026-11-05", "status": "EXPERIMENTAL_SENSITIVITY_ONLY",
              "pit_status": "PIT_BACKTEST_BLOCKED", "value": {}, "quality": {}, "garp": {}}
    # true global from raw values, with global winsorization
    g = value_global(v, (1, 99)); report["value"]["global_top50_overlap"] = len(vtop & top(g))
    report["value"]["global_raw_top50_overlap"] = len(vtop & top(value_global(v, (0, 100))))
    for w in ((5, 95), (10, 90)):
        report["value"][f"winsor_{w[0]}_{w[1]}_top50_overlap"] = len(vtop & top(value_global(v, w)))
    for m in VM:
        rr = {r["cik"]: val(r, m + "_percentile") for r in v if val(r, m + "_percentile") is not None}
        report["value"][f"single_{m}_top50_overlap"] = len(vtop & top(rr))
    report["value"].update({"candidate_count": 2529, "all_four_positive": len(v), "partial_count": 1679,
                            "global_method": "raw values -> winsor -> global percentile -> average"})
    # Quality: peer vs true global, alternate weights use published peer percentiles
    q = [r for r in load("quality_rankings.csv") if r.get("quality_status") == "QUALITY_V1_SCORED"]
    qtop = top({r["cik"]: val(r, "quality_score_recomputed") for r in q})
    qfields = {"roe": "roe", "roa": "roa", "cfo": "cfo_to_avg_assets", "leverage": "liabilities_to_assets"}
    qcols = {}
    for m in QM:
        vals = {r["cik"]: val(r, qfields[m]) for r in q if val(r, qfields[m]) is not None}
        qcols[m] = rank(vals, higher=(m != "leverage"))
    qcommon = set.intersection(*(set(x) for x in qcols.values()))
    qglobal = {c: .30*qcols["roe"][c] + .25*qcols["roa"][c] + .25*qcols["cfo"][c] + .20*qcols["leverage"][c] for c in qcommon}
    report["quality"]["global_top50_overlap"] = len(qtop & top(qglobal))
    variants = {"published": (.30, .25, .25, .20), "equal": (.25, .25, .25, .25),
                "roe_heavy": (.40, .20, .20, .20), "cfo_heavy": (.20, .20, .40, .20)}
    for name, w in variants.items():
        sc = {}
        for r in q:
            try:
                sc[r["cik"]] = sum(float(r[m + "_percentile"]) * x for m, x in zip(QM, w))
            except (TypeError, ValueError):
                pass
        report["quality"][f"{name}_top50_overlap"] = len(qtop & top(sc))
    report["quality"]["scored_count"] = len(q)
    report["quality"]["weight_note"] = "Top-50 overlap is not a performance result; no backtest."
    # GARP: count thresholds, 5Y inclusion, history length, global
    gr = [r for r in load("garp_rankings.csv") if r.get("garp_score") not in ("", None)]
    gtop = top({r["cik"]: val(r, "garp_score") for r in gr})
    for need in (3, 4, 5):
        sc = {}
        for r in gr:
            vals = [val(r, m + "_percentile") for m in GM if val(r, m + "_percentile") is not None]
            if len(vals) >= need: sc[r["cik"]] = sum(vals) / len(vals)
        report["garp"][f"min_{need}_top50_overlap"] = len(gtop & top(sc))
    sc = {}
    for r in gr:
        vals = [val(r, m + "_percentile") for m in GM if m != "revenue_cagr_5y" and val(r, m + "_percentile") is not None]
        if len(vals) >= 3: sc[r["cik"]] = sum(vals) / len(vals)
    report["garp"]["without_5y_top50_overlap"] = len(gtop & top(sc))
    for years in (3, 5, 7):
        sub = {r["cik"]: val(r, "garp_score") for r in gr if val(r, "history_years") is not None and float(r["history_years"]) >= years}
        report["garp"][f"history_ge_{years}y_top50_overlap"] = len(gtop & top(sub)) if len(sub) >= 50 else None
    gcols = {}
    for m in GM:
        vals = {r["cik"]: val(r, m) for r in gr if val(r, m) is not None}
        gcols[m] = rank(vals, higher=True)
    gg = {}
    for r in gr:
        c = r["cik"]; vals = [gcols[m][c] for m in GM if c in gcols[m]]
        if len(vals) >= 3: gg[c] = sum(vals) / len(vals)
    report["garp"]["global_top50_overlap"] = len(gtop & top(gg))
    report["garp"].update({"ranked_count": len(gr), "note": "global recomputed from raw historical metrics; 5Y included in current score"})
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
