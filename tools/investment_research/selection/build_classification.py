"""P6.15 issuer classification map: P6.5 SIC family + P6.8 accounting standard."""
from __future__ import annotations
import argparse, csv, json
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_SIC = Path("data/universe/selection_inputs/us_equity_industry_sic_p65.csv")
DEFAULT_READY = Path("data/universe/selection_inputs/value_v1_readiness_p68.csv")
DEFAULT_CURRENT = Path("data/universe/selection_inputs/us_equities_current.csv")
DEFAULT_OUT = Path("data/universe/selection_inputs/issuer_classification_p615.csv")
SPECIAL = {"BANKS", "INSURANCE", "REIT", "BDC", "OTHER_FINANCIALS", "UTILITIES", "ENERGY", "UNCLASSIFIED"}


def read(path):
    b = path.read_bytes()[:2]
    with path.open(encoding="utf-16" if b in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sic", type=Path, default=DEFAULT_SIC)
    ap.add_argument("--ready", type=Path, default=DEFAULT_READY)
    ap.add_argument("--current", type=Path, default=DEFAULT_CURRENT)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()
    current = read(a.current)
    sic = {}
    for r in read(a.sic):
        cik = (r.get("CIK") or "").zfill(10)
        if cik:
            sic.setdefault(cik, r)
    ready = {}
    for r in read(a.ready):
        cik = (r.get("cik") or "").zfill(10)
        if cik:
            ready.setdefault(cik, r)
    by_cik = defaultdict(list)
    for r in current:
        cik = (r.get("CIK") or "").zfill(10)
        if cik and r.get("security_type") in ("COMMON", "ADR"):
            by_cik[cik].append(r)
    rows = []
    for cik, rs in sorted(by_cik.items()):
        rs.sort(key=lambda x: (x.get("security_type") != "COMMON", x.get("ticker", "")))
        c = rs[0]; s = sic.get(cik); q = ready.get(cik)
        model = (s or {}).get("model_family") or "UNCLASSIFIED"
        acc = (q or {}).get("accounting_standard") or "NONE"
        status = "P6_5_MATCHED" if s and q else ("MODEL_ONLY" if s else "ACCOUNTING_ONLY" if q else "UNCLASSIFIED")
        rows.append({"ticker": c.get("ticker", ""), "cik": cik,
                     "company_name": c.get("security_name", ""),
                     "security_type": c.get("security_type", ""), "exchange": c.get("exchange", ""),
                     "listing_status": c.get("listing_status", ""),
                     "model_family": model, "accounting_standard": acc,
                     "special_model": "True" if model in SPECIAL else "False",
                     "classification_status": status,
                     "sic": (s or {}).get("sic", ""), "sic_description": (s or {}).get("sic_description", "")})
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(json.dumps({"out": str(a.out), "rows": len(rows), "model_counts": dict(Counter(r["model_family"] for r in rows)),
                      "accounting_counts": dict(Counter(r["accounting_standard"] for r in rows)),
                      "status_counts": dict(Counter(r["classification_status"] for r in rows))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
