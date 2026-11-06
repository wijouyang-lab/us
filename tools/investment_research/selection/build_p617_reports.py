"""P6.17 reconciliation and quality report."""
from __future__ import annotations
import csv, json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("data/universe/selection")
P616 = ROOT / "selection_quality_report.json"


def read(name):
    p = ROOT / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def rows(name):
    p = ROOT / name
    if not p.exists(): return []
    with p.open(encoding="utf-8", newline="") as f: return list(csv.DictReader(f))


def main():
    old = read("p616_tradability_baseline.json")
    p617 = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "CURRENT_CROSS_SECTIONAL_RESEARCH",
        "pit_status": "PIT_BACKTEST_BLOCKED",
        "research_label": "RESEARCH_ONLY_NOT_A_BUY_SELL_SIGNAL",
        "data_as_of": "2026-11-05",
        "p616": {"tradability": old.get("tradability", {}), "counts": old.get("counts", {}),
                 "valuation": old.get("valuation", {}).get("status_counts", {})},
        "valuation_recalculation": read("valuation_recalculation_summary_p617.json"),
        "filing_freshness": read("filing_freshness_summary_p617.json"),
        "liquidity_quality": read("liquidity_fetch_summary_p616.json"),
        "tradability": read("tradability/tradability_summary.json"),
        "special_models": read("special_model_coverage.json"),
    }
    recon = []
    for kind in ("value", "quality", "garp"):
        for r in rows(f"tradability/{kind}_tradable_candidates.csv"):
            recon.append({"ticker": r["ticker"], "cik": r["cik"], "ranking": kind,
                          "original_rank": r.get("value_rank") or r.get("quality_rank") or r.get("garp_rank", ""),
                          "raw_tradability_status": r.get("raw_tradability_status", ""),
                          "final_tradability_status": r.get("tradability_status", ""),
                          "freshness_status": r.get("freshness_status", ""),
                          "valuation_status": r.get("valuation_status", ""),
                          "sec_filing_status": r.get("sec_filing_status", ""),
                          "liquidity_quality_status": r.get("liquidity_quality_status", ""),
                          "final_reason": r.get("tradability_reason", ""),
                          "market_cap": r.get("market_cap", ""), "price": r.get("price", ""),
                          "price_asof": r.get("price_asof", ""), "adv20_usd": r.get("adv20_usd", ""),
                          "adv60_usd": r.get("adv60_usd", "")})
    out = ROOT / "tradability_reconciliation_p617.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(recon[0].keys())); w.writeheader(); w.writerows(recon)
    p617["tradability_reconciliation"] = {
        "rows": len(recon),
        "final_status_counts": {f"{k[0]}|{k[1]}": v for k, v in Counter((r["ranking"], r["final_tradability_status"]) for r in recon).items()},
        "downgraded": [r for r in recon if r["raw_tradability_status"] == "ELIGIBLE" and r["final_tradability_status"] != "ELIGIBLE"],
    }
    (ROOT / "selection_quality_report_p617.json").write_text(json.dumps(p617, indent=2), encoding="utf-8")
    print(json.dumps({"p616": p617["p616"]["tradability"], "p617": p617["tradability"],
                      "recalc": p617["valuation_recalculation"].get("status_counts"),
                      "filing": p617["filing_freshness"].get("status_counts")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
