"""Assemble the P6.16 selection quality report from audited components."""
from __future__ import annotations
import csv, json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("data/universe/selection")
OUT = ROOT / "selection_quality_report.json"


def read(name):
    p = ROOT / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def main():
    val = read("valuation_integrity_summary.json")
    fresh = read("freshness_summary.json")
    trade = read("tradability/tradability_summary.json")
    special = read("special_model_coverage.json")
    snap = read("selection_snapshot.json")
    dq = read("selection_data_quality.json")
    # Valuation-valid subset, preserving original ranking order.
    audit = {r["ticker"]: r for r in (list(csv.DictReader(open(ROOT / "valuation_integrity_audit.csv", encoding="utf-8")))
                                         if (ROOT / "valuation_integrity_audit.csv").exists() else [])}
    top = list(csv.DictReader(open(ROOT / "value_top50.csv", encoding="utf-8")))
    valid = [r for r in top if audit.get(r["ticker"], {}).get("valuation_status") == "VALUATION_VALID"]
    if valid:
        with (ROOT / "value_valuation_valid_top50.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(valid[0].keys())); w.writeheader(); w.writerows(valid)
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "CURRENT_CROSS_SECTIONAL_RESEARCH",
        "pit_status": "PIT_BACKTEST_BLOCKED",
        "research_label": "RESEARCH_ONLY_NOT_A_BUY_SELL_SIGNAL",
        "data_as_of": snap.get("data_as_of"),
        "counts": {
            "value_candidates": snap.get("value", {}).get("candidate_issuers"),
            "value_all_four": snap.get("value", {}).get("all_four_ranked"),
            "quality_scored": snap.get("quality", {}).get("scored_issuers"),
            "garp_ranked": snap.get("garp", {}).get("ranked_issuers"),
        },
        "valuation": val,
        "freshness": {k: {"status_counts": v.get("status_counts"), "fresh_scored": v.get("fresh_scored"),
                          "stale_excluded_from_fresh_top50": v.get("stale_excluded_from_fresh_top50")}
                      for k, v in fresh.get("rankings", {}).items()},
        "tradability": trade,
        "special_models": special,
        "data_quality": dq,
        "limits": ["PIT backtest blocked", "No Alpha or transaction-costed return",
                   "ADV is current 20/60 sessions; ELIGIBLE is a research screen",
                   "Special models are not implemented", "Stored filing metadata is not a full subsequent filing history"],
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(OUT), "counts": out["counts"],
                      "valuation": val.get("status_counts"), "tradability": {k: trade.get(k, {}).get("eligible") for k in ("value","quality","garp")}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
