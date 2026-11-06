"""P7.1: feed refreshed SEC facts into a new Value ranking version.

Quality ROA/leverage and GARP history are not present in the refreshed fact
table; those factors are not recomputed or zero-filled. Value only uses metrics
for which a new SEC fact exists.
"""
from __future__ import annotations
import csv, json, math
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

from tools.investment_research.selection.build_rankings import value_build, identity_map, read_csv

SEL = Path("data/universe/selection")
INPUTS = Path("data/universe/selection_inputs")
P7 = Path("data/universe/p7")
AS_OF = date(2026, 11, 5)


def num(v):
    try:
        x = float(v); return x if math.isfinite(x) else None
    except (TypeError, ValueError): return None


def main():
    old = read_csv(INPUTS / "value_metric_rankings_p69.csv")
    upd = {r["ticker"]: r for r in read_csv(P7 / "updated_fundamentals.csv")}
    identity, _ = identity_map(read_csv(INPUTS / "us_equities_current.csv"))
    rows = []
    changed = 0
    for r in old:
        r = dict(r); u = upd.get(r["ticker"])
        if u and u.get("refresh_status") == "UPDATED_FROM_SEC_COMPANYFACTS":
            changed += 1
            for src, dst in (("net_income", "net_income"), ("equity", "stockholders_equity"),
                             ("revenue", "revenue"), ("cfo", "operating_cash_flow"),
                             ("capex", "capital_expenditure"), ("fcf", "free_cash_flow")):
                if u.get(src) not in ("", None): r[dst] = u[src]
            if u.get("new_period"): r["financial_period"] = u["new_period"]
            if u.get("new_filed"): r["filed"] = u["new_filed"]
            if u.get("latest_periodic_accession"): r["accn"] = u["latest_periodic_accession"]
            mcap = num(r.get("market_cap_raw")); eq = num(r.get("stockholders_equity")); rev = num(r.get("revenue"))
            ni = num(r.get("net_income")); fcf = num(r.get("free_cash_flow"))
            r["pb"] = str(mcap / eq) if mcap and eq and eq > 0 else ""
            r["ps"] = str(mcap / rev) if mcap and rev and rev > 0 else ""
            r["earnings_yield"] = str(ni / mcap) if ni is not None and mcap and mcap > 0 else ""
            r["fcf_yield"] = str(fcf / mcap) if fcf is not None and mcap and mcap > 0 else ""
            r["pe_derived"] = str(mcap / ni) if ni and mcap else ""
            r["update_source"] = "P7_SEC_COMPANYFACTS"
        rows.append(r)
    vr, vtop = value_build(rows, identity)
    for r in vr: r["score_version"] = "P71_UPDATED_SEC_FACTS"
    out = P7
    with (out / "value_rankings_p71.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(dict.fromkeys([k for row in vr for k in row.keys()]))); w.writeheader(); w.writerows(vr)
    with (out / "value_top50_p71.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(dict.fromkeys([k for row in vtop for k in row.keys()]))); w.writeheader(); w.writerows(vtop[:50])
    comp = []
    old_top = {r["ticker"]: r for r in read_csv(SEL / "value_top50.csv")}
    for r in vtop[:50]:
        o = old_top.get(r["ticker"], {})
        comp.append({"ticker": r["ticker"], "new_rank": r.get("value_rank"), "old_rank": o.get("value_rank", ""),
                     "new_score": r.get("value_composite_experimental"), "old_score": o.get("value_composite_experimental", ""),
                     "changed": r.get("value_composite_experimental") != o.get("value_composite_experimental", ""),
                     "score_version": "P71_UPDATED_SEC_FACTS"})
    with (out / "value_score_comparison_p71.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(comp[0].keys())); w.writeheader(); w.writerows(comp)
    summary = {"generated_at": datetime.now(timezone.utc).isoformat(), "as_of": AS_OF.isoformat(),
               "updated_rows": changed, "value_rows": len(vr), "value_ranked": len(vtop),
               "old_top50": len(old_top), "new_top50": len(vtop[:50]),
               "top50_new_entrants": [x["ticker"] for x in comp if x["old_rank"] == ""],
               "status": "P71_VALUE_RECALCULATED", "quality_garp": "NOT_RECALCULATED_MISSING_ASSETS_OR_HISTORY"}
    (out / "p71_score_refresh_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
