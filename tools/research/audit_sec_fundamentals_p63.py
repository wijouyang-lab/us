"""Audit SEC CompanyFacts coverage for the P6.1 universe."""
from __future__ import annotations
import argparse, csv, gzip, json
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

UNIVERSE = Path("data/universe/us_equities_current.csv")
PANEL = Path("data/universe/sec_fundamentals_panel_p63.csv.gz")
META = Path("data/universe/sec_fundamentals_panel_p63_meta.json")
OUT_CSV = Path("data/universe/sec_fundamentals_coverage_p63.csv")
OUT_JSON = Path("data/universe/sec_fundamentals_audit_p63.json")
METRICS = ["Revenue", "NetIncome", "EPSBasic", "EPSDiluted", "TotalAssets", "StockholdersEquity",
           "OperatingCashFlow", "CapitalExpenditure", "CashAndCashEquivalents", "LongTermDebt",
           "CommonSharesOutstanding", "DividendsPaid"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", type=Path, default=UNIVERSE)
    ap.add_argument("--panel", type=Path, default=PANEL)
    ap.add_argument("--meta", type=Path, default=META)
    ap.add_argument("--out-csv", type=Path, default=OUT_CSV)
    ap.add_argument("--out-json", type=Path, default=OUT_JSON)
    a = ap.parse_args()
    with a.universe.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    target = [r for r in rows if r["security_type"] in ("COMMON", "ADR")]
    unclassified = [r for r in rows if r["security_type"] == "UNCLASSIFIED"]
    ciks = {(r["CIK"] or "").strip().zfill(10) for r in target if (r.get("CIK") or "").strip()}
    ciks |= {(r["CIK"] or "").strip().zfill(10) for r in unclassified if (r.get("CIK") or "").strip()}
    today = date.today()
    stats = defaultdict(lambda: {"rows": 0, "std": False, "us": False, "ifrs": False,
                                 "latest": "", "metrics_any": set(), "metrics_recent": set(),
                                 "period_types": Counter()})
    total_rows = 0
    with gzip.open(a.panel, "rt", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            cik = r["cik"].zfill(10)
            if cik not in ciks: continue
            total_rows += 1
            s = stats[cik]
            s["rows"] += 1
            if r["taxonomy"] == "us-gaap": s["us"] = True
            if r["taxonomy"] == "ifrs-full": s["ifrs"] = True
            if r["taxonomy"] in ("us-gaap", "ifrs-full", "dei", "srt"): s["std"] = True
            s["period_types"][r["period_type"]] += 1
            s["metrics_any"].add(r["metric"])
            s["latest"] = max(s["latest"], r.get("filed") or "")
            try:
                filed = date.fromisoformat((r.get("filed") or "")[:10])
                if (today - filed).days <= 365: s["metrics_recent"].add(r["metric"])
            except ValueError: pass
    # per-security coverage
    out_rows = []
    for r in target + unclassified:
        cik = (r.get("CIK") or "").strip().zfill(10) if (r.get("CIK") or "").strip() else ""
        s = stats.get(cik)
        rec = {"ticker": r["ticker"], "security_name": r["security_name"], "exchange": r["exchange"],
               "security_type": r["security_type"], "CIK": cik,
               "cohort": "TARGET" if r["security_type"] in ("COMMON", "ADR") else "UNCLASSIFIED",
               "companyfacts_found": bool(s and s["rows"]),
               "standard_facts": bool(s and s["std"]), "us_gaap_facts": bool(s and s["us"]),
               "ifrs_facts": bool(s and s["ifrs"]), "panel_rows": s["rows"] if s else 0,
               "latest_filed": s["latest"] if s else ""}
        for m in METRICS:
            rec[f"{m}_any"] = bool(s and m in s["metrics_any"])
            rec[f"{m}_recent"] = bool(s and m in s["metrics_recent"])
        out_rows.append(rec)
    a.out_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = list(out_rows[0].keys()) if out_rows else ["ticker"]
    with a.out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(out_rows)
    trows = [x for x in out_rows if x["cohort"] == "TARGET"]
    urows = [x for x in out_rows if x["cohort"] == "UNCLASSIFIED"]
    def cov(rs, key): return round(sum(1 for x in rs if x[key]) / len(rs), 6) if rs else None
    by_type = {}
    for typ in ("COMMON", "ADR", "UNCLASSIFIED"):
        rs = [x for x in out_rows if x["security_type"] == typ]
        by_type[typ] = {"records": len(rs), "with_cik": sum(1 for x in rs if x["CIK"]),
                        "companyfacts_found": sum(1 for x in rs if x["companyfacts_found"]),
                        "companyfacts_coverage": cov(rs, "companyfacts_found"),
                        "standard_facts": sum(1 for x in rs if x["standard_facts"]),
                        "us_gaap": sum(1 for x in rs if x["us_gaap_facts"]),
                        "ifrs": sum(1 for x in rs if x["ifrs_facts"])}
    by_exchange = {}
    for ex in sorted({x["exchange"] for x in trows}):
        rs = [x for x in trows if x["exchange"] == ex]
        by_exchange[ex] = {"records": len(rs), "found": sum(1 for x in rs if x["companyfacts_found"]),
                           "coverage": cov(rs, "companyfacts_found")}
    metric_summary = {}
    for m in METRICS:
        metric_summary[m] = {"any": sum(1 for x in trows if x[f"{m}_any"]),
                             "recent": sum(1 for x in trows if x[f"{m}_recent"]),
                             "any_coverage": round(sum(1 for x in trows if x[f"{m}_any"]) / len(trows), 6),
                             "recent_coverage": round(sum(1 for x in trows if x[f"{m}_recent"]) / len(trows), 6)}
    meta = json.loads(a.meta.read_text()) if a.meta.exists() else {}
    report = {"metadata": {"generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "SEC companyfacts.zip", "zip_metadata": meta,
        "scope": "P6.1 CURRENT COMMON + ADR; UNCLASSIFIED separate",
        "pit_rule": "filed -> next weekday; holidays not adjusted; no acceptanceDateTime",
        "note": "CompanyFacts presence is not the same as complete metric coverage; only standard taxonomies are mapped."},
        "counts": {"target_records": len(trows), "target_with_cik": sum(1 for x in trows if x["CIK"]),
                   "target_unique_ciks": len({x["CIK"] for x in trows if x["CIK"]}),
                   "target_missing_cik": sum(1 for x in trows if not x["CIK"]),
                   "unclassified_records": len(urows),
                   "unclassified_unique_ciks": len({x["CIK"] for x in urows if x["CIK"]}),
                   "panel_rows_for_targets": total_rows,
                   "unique_ciks_in_panel": len([c for c in ciks if stats[c]["rows"]])},
        "by_type": by_type, "by_exchange": by_exchange, "metrics": metric_summary,
        "missing_companyfacts_tickers": [x["ticker"] for x in trows if not x["companyfacts_found"]][:200],
        "missing_companyfacts_count": sum(1 for x in trows if not x["companyfacts_found"]),
        "unclassified_companyfacts": {"records": len(urows), "found": sum(1 for x in urows if x["companyfacts_found"]),
                                      "standard": sum(1 for x in urows if x["standard_facts"])}}
    a.out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"counts": report["counts"], "by_type": by_type,
                      "metrics": metric_summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
