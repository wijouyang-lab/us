"""P6.5: re-audit Quality readiness after SEC SIC enrichment."""
from __future__ import annotations
import argparse, csv, gzip, json
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

CURRENT = Path("data/universe/us_equities_current.csv")
INDUSTRY = Path("data/universe/us_equity_industry_sic_p65.csv")
COV = Path("data/universe/sec_fundamentals_coverage_p63.csv")
P64 = Path("data/universe/us_equity_style_readiness_p64.csv")
PANEL = Path("data/universe/sec_fundamentals_panel_p63.csv.gz")
OUT = Path("data/universe/us_equity_quality_readiness_p65.csv")
REPORT = Path("data/universe/us_equity_industry_coverage_p65.json")
SPECIAL = {"BANKS","INSURANCE","OTHER_FINANCIALS","REIT","BDC","UTILITIES","ENERGY"}
STANDARD = {"MATERIALS","INDUSTRIALS","TECHNOLOGY","COMMUNICATIONS","HEALTHCARE",
            "CONSUMER_DISCRETIONARY","CONSUMER_STAPLES","OTHER_SERVICES"}


def b(v): return str(v).strip().lower() in ("true","1","yes","y")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", type=Path, default=PANEL)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--report", type=Path, default=REPORT)
    a = ap.parse_args()
    if not a.panel.exists(): print("P6.3 PANEL ARTIFACT MISSING"); return 2
    with CURRENT.open(encoding="utf-8") as f: uni = list(csv.DictReader(f))
    with INDUSTRY.open(encoding="utf-8") as f: inds = {r["ticker"]: r for r in csv.DictReader(f)}
    with COV.open(encoding="utf-8") as f: covs = {r["ticker"]: r for r in csv.DictReader(f)}
    old = {}
    if P64.exists():
        with P64.open(encoding="utf-8") as f:
            old = {r["ticker"]: b(r.get("quality_input_ready")) for r in csv.DictReader(f)}
    stats = defaultdict(lambda: {"annual": Counter(), "instant": Counter(), "latest": ""})
    with gzip.open(a.panel, "rt", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            cik = (r.get("cik") or "").zfill(10); s = stats[cik]
            if r["period_type"] == "ANNUAL": s["annual"][r["metric"]] += 1
            if r["period_type"] == "INSTANT": s["instant"][r["metric"]] += 1
            s["latest"] = max(s["latest"], r.get("filed") or "")
    rows = []
    for u in uni:
        t = u["ticker"]; ci = inds.get(t, {})
        c = covs.get(t, {}); s = stats.get((u.get("CIK") or "").zfill(10), {})
        acc = "MIXED" if b(c.get("us_gaap_facts")) and b(c.get("ifrs_facts")) else \
              "US_GAAP" if b(c.get("us_gaap_facts")) else "IFRS" if b(c.get("ifrs_facts")) else "NONE"
        family = ci.get("model_family") or "UNCLASSIFIED"
        found = b(c.get("companyfacts_found")); std = b(c.get("standard_facts"))
        metrics = {m: b(c.get(m + "_any")) for m in
                   ("Revenue","NetIncome","TotalAssets","StockholdersEquity","OperatingCashFlow")}
        ann = (s or {}).get("annual", {}); inst = (s or {}).get("instant", {})
        hist_ok = (ann.get("NetIncome", 0) >= 2 and inst.get("TotalAssets", 0) >= 2
                   and inst.get("StockholdersEquity", 0) >= 2)
        data_avail = found and std and acc in ("US_GAAP","IFRS") and hist_ok and all(metrics.values())
        special = family in SPECIAL
        std_family = family in STANDARD
        input_ready = data_avail and std_family and acc in ("US_GAAP","IFRS")
        industry_missing = family == "UNCLASSIFIED"
        acct_blocked = acc in ("MIXED","NONE")
        blockers = []
        if not data_avail: blockers.append("QUALITY_DATA_INCOMPLETE")
        if special: blockers.append("QUALITY_SPECIAL_MODEL_REQUIRED")
        if industry_missing: blockers.append("QUALITY_INDUSTRY_MISSING")
        if acct_blocked: blockers.append("QUALITY_ACCOUNTING_STANDARD_BLOCKED")
        rows.append({"ticker": t, "cik": u.get("CIK") or "", "exchange": u["exchange"],
                     "security_type": u["security_type"], "model_family": family,
                     "special_model": special, "accounting_standard": acc,
                     "sic": ci.get("sic", ""), "sic_description": ci.get("sic_description", ""),
                     "annual_netincome_observations": ann.get("NetIncome", 0),
                     "instant_assets_observations": inst.get("TotalAssets", 0),
                     "instant_equity_observations": inst.get("StockholdersEquity", 0),
                     "quality_data_available": data_avail,
                     "quality_standard_model_input_ready": input_ready,
                     "quality_special_model_required": special and data_avail,
                     "quality_industry_missing": industry_missing,
                     "quality_accounting_standard_blocked": acct_blocked,
                     "blocker_codes": "|".join(blockers),
                     "data_as_of": c.get("latest_filed") or (s or {}).get("latest", "")})
    target = [r for r in rows if r["security_type"] in ("COMMON","ADR")]
    unclass = [r for r in rows if r["security_type"] == "UNCLASSIFIED"]
    def count(rs, key): return sum(1 for r in rs if r[key])
    new_ready = {r["ticker"] for r in target if r["quality_standard_model_input_ready"]}
    old_set = {t for t, v in old.items() if v}
    lost = sorted(old_set - new_ready)
    gained = sorted(new_ready - old_set)
    by_type = {}
    for typ in ("COMMON","ADR"):
        rs = [r for r in target if r["security_type"] == typ]
        by_type[typ] = {"records": len(rs), "data_available": count(rs,"quality_data_available"),
                        "input_ready": count(rs,"quality_standard_model_input_ready"),
                        "special": count(rs,"quality_special_model_required"),
                        "industry_missing": count(rs,"quality_industry_missing")}
    by_exchange = {}
    for ex in sorted({r["exchange"] for r in target}):
        rs = [r for r in target if r["exchange"] == ex]
        by_exchange[ex] = {"records": len(rs), "input_ready": count(rs,"quality_standard_model_input_ready")}
    by_family = {}
    for fam in sorted({r["model_family"] for r in target}):
        rs = [r for r in target if r["model_family"] == fam]
        by_family[fam] = {"records": len(rs), "data_available": count(rs,"quality_data_available"),
                          "input_ready": count(rs,"quality_standard_model_input_ready"),
                          "special": fam in SPECIAL}
    by_acc = {}
    for acc in sorted({r["accounting_standard"] for r in target}):
        rs = [r for r in target if r["accounting_standard"] == acc]
        by_acc[acc] = {"records": len(rs), "input_ready": count(rs,"quality_standard_model_input_ready")}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    report = {
        "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(),
                     "scope": "P6.4 Quality rules with P6.5 SIC model families",
                     "panel": str(a.panel), "sic_source": "data/universe/us_equity_industry_sic_p65.csv"},
        "counts": {"target_records": len(target), "unique_ciks": len({r["cik"] for r in target if r["cik"]}),
                   "standard_model_data_available": count(target,"quality_data_available"),
                   "standard_model_input_ready": len(new_ready),
                   "special_model_required": count(target,"quality_special_model_required"),
                   "industry_missing": count(target,"quality_industry_missing"),
                   "accounting_standard_blocked": count(target,"quality_accounting_standard_blocked"),
                   "unclassified_records": len(unclass),
                   "unclassified_input_ready": count(unclass,"quality_standard_model_input_ready")},
        "by_type": by_type, "by_exchange": by_exchange, "by_family": by_family,
        "by_accounting": by_acc,
        "reproduction": {"old_p64_input_ready": len(old_set), "new_input_ready": len(new_ready),
                         "intersection": len(old_set & new_ready), "lost_count": len(lost),
                         "gained_count": len(gained), "lost_examples": lost[:50],
                         "gained_examples": gained[:50]},
        "family_counts": {k: sum(1 for r in target if r["model_family"] == k) for k in
                          ("BANKS","INSURANCE","REIT","BDC","OTHER_FINANCIALS","UNCLASSIFIED")},
        "notes": ["SIC is not GICS.", "Special families are not forced into the standard Quality model.",
                  "Input readiness still requires the P6.4 financial-history and accounting gates."]
    }
    existing = json.loads(a.report.read_text(encoding="utf-8")) if a.report.exists() else {}
    existing["quality"] = report
    a.report.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report["counts"], indent=2))
    print(json.dumps(report["reproduction"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
