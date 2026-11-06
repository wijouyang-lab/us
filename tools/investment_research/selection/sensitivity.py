"""P6.14 sensitivity checks for the experimental Value/Quality rankings."""
from __future__ import annotations
import csv, json, math
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("data/universe/selection")
OUT = ROOT / "selection_sensitivity.json"
VM = ("pb", "ps", "earnings_yield", "fcf_yield")
QM = ("roe", "roa", "cfo", "leverage")


def load(name):
    with (ROOT / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_raw_value():
    p = Path("data/universe/selection_inputs/value_metric_rankings_p69.csv")
    with p.open(encoding="utf-8", newline="") as f:
        return {r["cik"].zfill(10): r for r in csv.DictReader(f)}


def pct_map(items, higher=True):
    if not items: return {}
    s = pd.Series({k: v for k, v in items}, dtype=float).rank(pct=True, method="average") * 100
    return {k: (v if higher else 100-v) for k, v in s.items()}


def top(rows, key, n=50):
    return {r["cik"] for r in sorted(rows, key=lambda r: (-float(r[key]), r["ticker"], r["cik"]))[:n]}


def main():
    v = load("value_rankings.csv")
    va = [r for r in v if r["value_composite_experimental"]]
    current = top(va, "value_composite_experimental")
    report = {"generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
              "data_as_of": "2026-11-05", "value": {}, "quality": {}}
    # single-factor top50 vs experimental composite
    for m in VM:
        key = m + "_percentile"
        r = [x for x in va if x.get(key) not in ("", None)]
        report["value"][f"single_{m}_top50_overlap"] = len(current & top(r, key))
    # global (no peer group) composite
    global_rows = []
    for r in va:
        try:
            global_rows.append({**r, "_global": sum(float(r[m + "_percentile"]) for m in VM) / 4})
        except (TypeError, ValueError):
            continue
    report["value"]["global_rank_top50_overlap"] = len(current & top(global_rows, "_global"))
    # raw (unwinsorized) percentiles: use P6.9 raw fields
    raw_rows = []
    raw_src = load_raw_value()
    for r in va:
        src = raw_src.get(r["cik"], {})
        vals = []
        for m in VM:
            try: vals.append(float(src[m + "_percentile_raw"]))
            except (KeyError, TypeError, ValueError): vals = []; break
        if len(vals) == 4:
            raw_rows.append({**r, "_raw": sum(vals) / 4})
    report["value"]["raw_pct_top50_overlap"] = len(current & top(raw_rows, "_raw"))
    # missing data impact
    report["value"]["candidate_count"] = sum(1 for r in v if r["candidate"] == "True")
    report["value"]["all_four_positive"] = len(va)
    report["value"]["partial_count"] = sum(1 for r in v if r["value_status"] == "VALUE_PARTIAL")
    # quality alternate weights
    q = [r for r in load("quality_rankings.csv") if r["quality_status"] == "QUALITY_V1_SCORED"]
    qcur = top(q, "quality_score_recomputed")
    variants = {"published": {k: w for k, w in zip(QM, (.30,.25,.25,.20))},
                "equal": {k: .25 for k in QM},
                "roe_heavy": {"roe": .40, "roa": .20, "cfo": .20, "leverage": .20},
                "cfo_heavy": {"roe": .20, "roa": .20, "cfo": .40, "leverage": .20}}
    for name, w in variants.items():
        rows = []
        for r in q:
            try:
                rows.append({**r, "_score": sum(float(r[k + "_percentile"]) * w[k] for k in QM)})
            except (TypeError, ValueError):
                pass
        report["quality"][f"{name}_top50_overlap"] = len(qcur & top(rows, "_score"))
    qglobal = []
    for r in q:
        try: qglobal.append({**r, "_global": sum(float(r[k + "_percentile"]) for k in QM) / 4})
        except (TypeError, ValueError): pass
    report["quality"]["global_no_peer_top50_overlap"] = len(qcur & top(qglobal, "_global"))
    report["quality"]["scored_count"] = len(q)
    report["quality"]["weight_note"] = "Top-50 overlap is not a performance result; no backtest."
    report["status"] = "EXPERIMENTAL_SENSITIVITY_ONLY"
    report["pit_status"] = "PIT_BACKTEST_BLOCKED"
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
