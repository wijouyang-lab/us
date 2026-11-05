"""Verify P6.10 Earnings Yield study outputs and add audit checks."""
from __future__ import annotations
import argparse, csv, json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SCORES = Path("data/universe/earnings_yield_v1_scores_p610.csv")
COV = Path("data/universe/earnings_yield_coverage_p610.json")
CORR = Path("data/universe/earnings_yield_correlation_p610.json")
ROBUST = Path("data/universe/earnings_yield_robustness_p610.json")
QUAD = Path("data/universe/earnings_yield_quality_quadrants_p610.csv")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", type=Path, default=SCORES)
    ap.add_argument("--coverage", type=Path, default=COV)
    ap.add_argument("--corr", type=Path, default=CORR)
    ap.add_argument("--robust", type=Path, default=ROBUST)
    ap.add_argument("--quad", type=Path, default=QUAD)
    a = ap.parse_args()
    rows = list(csv.DictReader(a.scores.open(encoding="utf-8")))
    target = [r for r in rows if r["security_type"] in ("COMMON","ADR")]
    cand = [r for r in target if r["candidate"] == "True"]
    checks = {
        "candidates_2529": len(cand) == 2529,
        "unique_cik_2529": len({r["cik"] for r in cand}) == 2529,
        "ey_valid_2504": sum(1 for r in cand if r["earnings_yield"] and r["financial_period_invalid"] != "True") == 2504,
        "negative_ey_retained": any(float(r["earnings_yield"]) < 0 for r in cand if r["earnings_yield"]),
        "missing_ey_not_zero": all(r["earnings_yield"] == "" for r in cand if r["status"] == "METRIC_BLOCKED" and "NET_INCOME_MISSING" in r["blocker_codes"]),
        "no_adr_candidates": all(r["security_type"] == "COMMON" for r in cand),
        "invalid_period_not_ranked": all(r["status"] != "METRIC_RANK_AVAILABLE" for r in cand if r["financial_period_invalid"] == "True"),
    }
    cov = json.loads(a.coverage.read_text(encoding="utf-8"))
    corr = json.loads(a.corr.read_text(encoding="utf-8"))
    rob = json.loads(a.robust.read_text(encoding="utf-8"))
    qrows = list(csv.DictReader(a.quad.open(encoding="utf-8")))
    checks["pe_ey_minus_one"] = corr["pe_ey"]["spearman"] == -1.0
    checks["ey_fcf_positive"] = corr["pairs"]["EY_FCF"]["spearman"] > 0
    checks["ey_quality_positive"] = corr["pairs"]["EY_Quality"]["spearman"] > 0
    checks["winsor_rank_high"] = rob["winsorization"]["spearman"] > 0.99
    checks["peer_insufficient_55"] = sum(1 for r in cand if r["status"] == "INSUFFICIENT_PEER_GROUP") == 55
    checks["historical_gate_false"] = cov["historical_gate"]["backtest_ready"] is False
    checks["quadrant_total"] = sum(int(r["n"]) for r in qrows) == 1727
    checks["no_composite_column"] = "composite" not in list(rows[0].keys())
    coverage = {"verified_at": datetime.now(timezone.utc).isoformat(), "checks": checks,
                "all_checks_pass": all(checks.values()), "candidates": len(cand),
                "ey_valid": cov["pool"]["ey_valid"], "ey_ranked": cov["pool"]["ey_ranked"],
                "category_counts": {k: v["n"] for k, v in cov["categories"].items()},
                "quadrants": {r["quadrant"]: int(r["n"]) for r in qrows},
                "historical_gate": cov["historical_gate"]}
    cov["verification"] = coverage
    a.coverage.write_text(json.dumps(cov, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(coverage, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
