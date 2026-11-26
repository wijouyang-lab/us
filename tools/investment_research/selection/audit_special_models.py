"""P6.16 special-model and BDC classification audit."""
from __future__ import annotations
import csv, json, re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("data/universe/selection")
INPUTS = Path("data/universe/selection_inputs")
CLASS = INPUTS / "issuer_classification_p615.csv"
SIC = INPUTS / "us_equity_industry_sic_p65.csv"
GARP = ROOT / "garp_rankings.csv"
CURRENT = INPUTS / "us_equities_current.csv"
OUT = ROOT / "special_model_coverage.json"


def read(p):
    b = p.read_bytes()[:2]
    with p.open(encoding="utf-16" if b in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    cls = read(CLASS); sic = {r["ticker"]: r for r in read(SIC)}
    garp = read(GARP); current = read(CURRENT)
    families = ("BANKS", "INSURANCE", "REIT", "BDC", "OTHER_FINANCIALS", "UTILITIES", "ENERGY", "UNCLASSIFIED")
    coverage = {f: {"value_rows": 0, "quality_rows": 0, "garp_rows": 0} for f in families}
    for kind, file in (("value", "value_rankings.csv"), ("quality", "quality_rankings.csv"), ("garp", "garp_rankings.csv")):
        for r in read(ROOT / file):
            fam = r.get("model_family") or "UNCLASSIFIED"
            if fam in coverage: coverage[fam][kind + "_rows"] += 1
    # BDC names are a heuristic identity audit, not a confirmed SEC classification.
    bdc_name = []
    for r in current:
        if r.get("security_type") != "COMMON": continue
        n = r.get("security_name", "")
        if re.search(r"\bBDC\b|Business Development", n, re.I):
            bdc_name.append(r["ticker"])
    blocked = [r for r in garp if r.get("garp_status") == "GARP_CLASSIFICATION_BLOCKED"]
    comp = Counter((r.get("model_family"), r.get("accounting_standard")) for r in blocked)
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "special_models": coverage,
        "bdc_audit": {
            "explicit_bdc_model_family_rows": coverage["BDC"]["value_rows"],
            "sic_6726_rows": sum(1 for r in sic.values() if r.get("sic") == "6726"),
            "bdc_name_candidates": sorted(set(bdc_name)),
            "bdc_name_candidate_count": len(set(bdc_name)),
            "bdc_candidate_classifications": sorted({(r.get("model_family"), r.get("accounting_standard"))
                                                    for r in cls if r["ticker"] in set(bdc_name)}),
            "note": "0 explicit BDC rows does not mean no BDCs. Known BDC-name candidates are largely UNCLASSIFIED because SIC is missing; no BDC model was invented.",
        },
        "classification_blocked": {
            "garp_blocked": len(blocked),
            "unclassified_none": comp.get(("UNCLASSIFIED", "NONE"), 0),
            "unclassified_us_gaap": comp.get(("UNCLASSIFIED", "US_GAAP"), 0),
            "unsupported_accounting": sum(v for (m, a), v in comp.items() if a not in ("US_GAAP", "IFRS")),
            "composition": {f"{m}|{a}": v for (m, a), v in comp.items()},
        },
        "implementable": {
            "BANKS": "P/B + ROE data exists; specialized capital quality not yet validated",
            "INSURANCE": "P/B + ROE data exists; underwriting/capital fields missing",
            "REIT": "P/FFO, AFFO and NAV not available; SPECIAL_MODEL_REQUIRED",
            "BDC": "NAV/credit and explicit BDC identity unavailable; BLOCKED",
            "UTILITIES": "generic cash/asset metrics only; no specialized model",
            "ENERGY": "generic cash/asset metrics only; no specialized model",
        },
        "status": "SPECIAL_MODEL_REQUIRED_NOT_IMPLEMENTED",
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"bdc": out["bdc_audit"], "blocked": out["classification_blocked"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
