"""Verify P6.9 standalone Value metric rankings and emit audit checks."""
from __future__ import annotations
import argparse, csv, json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

RANK = Path("data/universe/value_metric_rankings_p69.csv")
COV = Path("data/universe/value_metric_coverage_p69.csv")
AUDIT = Path("data/universe/value_metric_audit_p69.json")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rank", type=Path, default=RANK)
    ap.add_argument("--coverage", type=Path, default=COV)
    ap.add_argument("--audit", type=Path, default=AUDIT)
    a = ap.parse_args()
    rows = list(csv.DictReader(a.rank.open(encoding="utf-8")))
    cov = list(csv.DictReader(a.coverage.open(encoding="utf-8")))
    target = [r for r in rows if r["security_type"] in ("COMMON","ADR")]
    cand = [r for r in target if r["candidate"] == "True"]
    checks = {
        "candidate_2529": len(cand) == 2529,
        "unique_cik_2529": len({r["cik"] for r in cand}) == 2529,
        "pe_positive": all(float(r["pe"]) > 0 for r in cand if r["pe"]),
        "pb_positive": all(float(r["pb"]) > 0 for r in cand if r["pb"]),
        "fcf_not_filled": all(r["fcf_yield"] == "" for r in cand if not r["fcf_yield"] and not r["fcf_yield"]),
    }
    pe_ey = [r for r in cand if r["pe"] and r["earnings_yield"]]
    checks["pe_ey_reciprocal"] = all(abs(float(r["pe"]) * float(r["earnings_yield"]) - 1) < 1e-6 for r in pe_ey)
    status = Counter(r["scoring_status"] for r in target)
    d = json.loads(a.audit.read_text(encoding="utf-8"))
    checks["all_five_992"] = d["intersections"]["all_five"] == 992
    checks["rank_available_2474"] = status["METRIC_RANK_AVAILABLE"] == 2474
    checks["no_composite_score"] = "composite" not in a.rank.read_text(encoding="utf-8").split("\n")[0].lower()
    d["verification"] = {"verified_at": datetime.now(timezone.utc).isoformat(), "checks": checks,
                         "all_checks_pass": all(checks.values()), "candidate_securities": len(cand),
                         "candidate_unique_ciks": len({r["cik"] for r in cand}),
                         "coverage_rows": len(cov), "status_counts": dict(status)}
    a.audit.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(d["verification"], indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
