"""Audit and verify the P6.6 Quality V1 score outputs."""
from __future__ import annotations
import argparse, csv, json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SCORES = Path("data/universe/quality_v1_scores_p66.csv")
METRICS = Path("data/universe/quality_v1_metric_coverage_p66.csv")
AUDIT = Path("data/universe/quality_v1_scoring_audit_p66.json")
SPEC = Path("data/universe/quality_v1_model_spec_p66.json")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", type=Path, default=SCORES)
    ap.add_argument("--metrics", type=Path, default=METRICS)
    ap.add_argument("--audit", type=Path, default=AUDIT)
    ap.add_argument("--spec", type=Path, default=SPEC)
    a = ap.parse_args()
    rows = list(csv.DictReader(a.scores.open(encoding="utf-8")))
    target = [r for r in rows if r["security_type"] in ("COMMON","ADR")]
    candidates = [r for r in target if r["candidate"] == "True"]
    scored = [r for r in target if r["scoring_status"] == "QUALITY_V1_SCORED"]
    status = Counter(r["scoring_status"] for r in target)
    by_acc = {}
    for acc in sorted({r["accounting_standard"] for r in target}):
        rs = [r for r in target if r["accounting_standard"] == acc]
        by_acc[acc] = {"records": len(rs), "scored": sum(1 for r in rs if r["scoring_status"]=="QUALITY_V1_SCORED")}
    by_family = {}
    for fam in sorted({r["model_family"] for r in target}):
        rs = [r for r in target if r["model_family"] == fam]
        by_family[fam] = {"records": len(rs), "scored": sum(1 for r in rs if r["scoring_status"]=="QUALITY_V1_SCORED")}
    groups = {}
    for key in sorted({(r["model_family"], r["accounting_standard"]) for r in candidates}):
        rs = [r for r in candidates if (r["model_family"], r["accounting_standard"]) == key]
        scored_rs = [r for r in rs if r["scoring_status"] == "QUALITY_V1_SCORED"]
        groups[f"{key[0]}|{key[1]}"] = {"records": len(rs), "scored": len(scored_rs),
                                        "status": "SCORED" if scored_rs else ("INSUFFICIENT_PEER_GROUP" if len({r['cik'] for r in rs}) < 30 else "NO_COMPLETE")}
    tops = {}
    for key, g in groups.items():
        fam, acc = key.split("|", 1)
        rs = [r for r in scored if r["model_family"] == fam and r["accounting_standard"] == acc]
        rs.sort(key=lambda r: float(r["quality_v1_score"]), reverse=True)
        tops[key] = [{"ticker": r["ticker"], "cik": r["cik"], "score": round(float(r["quality_v1_score"]), 2)} for r in rs[:10]]
    existing = json.loads(a.audit.read_text(encoding="utf-8")) if a.audit.exists() else {}
    def fnum(v):
        try: return float(v)
        except (TypeError, ValueError): return None
    values = [fnum(r["quality_v1_score"]) for r in scored]
    values = [v for v in values if v is not None]
    distribution = {"count": len(values), "min": min(values) if values else None,
                    "max": max(values) if values else None,
                    "median": sorted(values)[len(values)//2] if values else None}
    extreme = {
        "roe_gt_2_or_lt_minus_1": sum(1 for r in scored if fnum(r["roe"]) is not None and (fnum(r["roe"]) > 2 or fnum(r["roe"]) < -1)),
        "roa_gt_1": sum(1 for r in scored if fnum(r["roa"]) is not None and fnum(r["roa"]) > 1),
        "leverage_gt_2": sum(1 for r in scored if fnum(r["liabilities_to_assets"]) is not None and fnum(r["liabilities_to_assets"]) > 2),
        "negative_avg_equity": sum(1 for r in scored if fnum(r["avg_equity"]) is not None and fnum(r["avg_equity"]) < 0),
    }
    checks = {
        "candidate_securities_3342": len(candidates) == 3342,
        "scored_securities_2335": len(scored) == 2335,
        "all_scored_have_score": all(r["quality_v1_score"] for r in scored),
        "all_scored_have_rank": all(r["quality_v1_rank"] for r in scored),
        "special_not_scored": all(r["scoring_status"] != "QUALITY_V1_SCORED" for r in target if r["model_family"] in
                                  ("BANKS","INSURANCE","REIT","BDC","OTHER_FINANCIALS","UTILITIES","ENERGY")),
    }
    existing["verification"] = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "candidate_securities": len(candidates),
        "scored_securities": len(scored),
        "status_counts": dict(status),
        "by_accounting": by_acc,
        "by_family": by_family,
        "group_verification": groups,
        "top10_by_group": tops,
        "all_checks_pass": all(checks.values()),
        "score_distribution": distribution,
        "extreme_values": extreme,
    }
    a.audit.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(existing["verification"], indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
