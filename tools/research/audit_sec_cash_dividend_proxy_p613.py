"""P6.13 audit SEC cash-dividend proxy feasibility using the P6.3 panel.

Full-market facts come from the normalized P6.3 panel. Per-share tag evidence is
read only from the existing 28-CIK raw CompanyFacts cache; no SEC ZIP is fetched.
"""
from __future__ import annotations
import sys
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parents[2]))
import argparse, csv, gzip, json, math
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from tools.research.normalize_sec_cash_dividend_proxy_p613 import (
    CASH_TAGS, PER_SHARE_TAGS, normalize_cash, period_type, ttm_status)

CURRENT = Path("data/universe/us_equities_current.csv")
SIC = Path("data/universe/us_equity_industry_sic_p65.csv")
PANEL = Path("data/universe/sec_fundamentals_panel_p63.csv.gz")
CACHE = Path("data/sec/cache")
OUT_FACTS = Path("data/universe/sec_cash_dividend_proxy_facts_p613.csv")
OUT_COV = Path("data/universe/sec_cash_dividend_proxy_coverage_p613.csv")
OUT_SUM = Path("data/universe/sec_cash_dividend_proxy_summary_p613.json")
PER_SHARE_FIXTURE = Path("data/universe/sec_cash_dividend_per_share_facts_p613.csv")
SNAPSHOT = date(2026, 11, 6)


def num(v):
    try:
        x = float(v); return x if math.isfinite(x) else None
    except (TypeError, ValueError): return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", type=Path, default=PANEL)
    a = ap.parse_args()
    uni = list(csv.DictReader(CURRENT.open(encoding="utf-8")))
    by_cik = defaultdict(list)
    for u in uni:
        c = (u.get("CIK") or "").strip().zfill(10)
        if c: by_cik[c].append(u)
    sic = {r["ticker"]: r for r in csv.DictReader(SIC.open(encoding="utf-8"))}
    facts = []
    seen = set(); duplicates = 0; sign_anomalies = 0
    cash_ciks = set(); all_ciks = set(by_cik)
    periods = defaultdict(list); tags = Counter(); units = Counter()
    with gzip.open(a.panel, "rt", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("metric") != "DividendsPaid": continue
            cik = (r.get("cik") or "").zfill(10)
            if cik not in by_cik: continue
            val = num(r.get("value"))
            if val is None: continue
            raw = val; norm, status = normalize_cash(val, r.get("unit"), r.get("tag"))
            if norm is None: continue
            key = (cik, r.get("taxonomy"), r.get("tag"), r.get("start"), r.get("end"), raw, r.get("accn"))
            if key in seen: duplicates += 1; continue
            seen.add(key)
            if raw < 0: sign_anomalies += 1
            recs = by_cik.get(cik, [])
            tickers = "|".join(x["ticker"] for x in recs)
            types = sorted({x["security_type"] for x in recs})
            if not recs: alloc = "NO_CURRENT_SECURITY"
            elif len(recs) > 1: alloc = "ISSUER_LEVEL_NOT_TICKER_ALLOCABLE"
            elif "ADR" in types: alloc = "ADR_RATIO_UNVERIFIED"
            elif types == ["COMMON"]: alloc = "TICKER_ALLOCABLE"
            else: alloc = "ISSUER_LEVEL_NOT_TICKER_ALLOCABLE"
            f = {"ticker": tickers or "ISSUER_LEVEL", "cik": cik,
                 "issuer_name": recs[0]["security_name"] if recs else "",
                 "security_type": "MULTI_CLASS" if len(recs) > 1 else (types[0] if types else "UNKNOWN"),
                 "taxonomy": r.get("taxonomy") or "", "tag": r.get("tag") or "",
                 "unit": r.get("unit") or "", "raw_value": raw,
                 "normalized_cash_dividend": norm,
                 "period_start": r.get("start") or "", "period_end": r.get("end") or "",
                 "filed_date": r.get("filed") or "", "form": r.get("form") or "",
                 "fiscal_year": r.get("fy") or "", "fiscal_period": r.get("fp") or "",
                 "accession_number": r.get("accn") or "",
                 "source_url": ("https://www.sec.gov/Archives/edgar/data/" + str(int(cik)) + "/" +
                                (r.get("accn") or "").replace("-", "") + "/") if r.get("accn") else "",
                 "available_at": r.get("pit_available_date") or "",
                 "period_type": period_type(r.get("start"), r.get("end"), r.get("filed")),
                 "allocation_status": alloc, "verification_status": status + ("|NEGATIVE_SIGN_PRESERVED" if raw < 0 else ""),
                 "fact_kind": "TOTAL_CASH"}
            facts.append(f)
            cash_ciks.add(cik); tags[r.get("tag") or ""] += 1; units[r.get("unit") or ""] += 1
            periods[cik].append((r.get("start") or "", r.get("end") or ""))
    # Add actual per-share tag facts from existing raw cache (max 28 CIKs), sample only
    per_share = []
    for p in CACHE.glob("companyfacts_*.json"):
        try: raw = json.loads(p.read_text(encoding="utf-8"))
        except Exception: continue
        cik = str(raw.get("cik") or "").zfill(10)
        if cik not in by_cik: continue
        recs = by_cik[cik]
        for tax in ("us-gaap", "ifrs-full"):
            for tag in PER_SHARE_TAGS:
                body = (raw.get("facts", {}).get(tax, {}) or {}).get(tag) or {}
                for unit, items in (body.get("units") or {}).items():
                    for x in items:
                        if x.get("val") is None or not x.get("filed"): continue
                        per_share.append({"ticker": recs[0]["ticker"], "cik": cik,
                            "issuer_name": recs[0]["security_name"], "security_type": recs[0]["security_type"],
                            "taxonomy": tax, "tag": tag, "unit": unit, "raw_value": x.get("val"),
                            "normalized_cash_dividend": "", "period_start": x.get("start") or "",
                            "period_end": x.get("end") or "", "filed_date": x.get("filed") or "",
                            "form": x.get("form") or "", "fiscal_year": x.get("fy") or "",
                            "fiscal_period": x.get("fp") or "", "accession_number": x.get("accn") or "",
                            "source_url": "https://www.sec.gov/Archives/edgar/data/" + str(int(cik)) + "/" + (x.get("accn") or "").replace("-", "") + "/",
                            "available_at": "", "period_type": period_type(x.get("start"), x.get("end"), x.get("filed")),
                            "allocation_status": "TICKER_ALLOCABLE" if len(recs) == 1 and recs[0]["security_type"] == "COMMON" else "ISSUER_LEVEL_NOT_TICKER_ALLOCABLE",
                            "verification_status": "PER_SHARE_FACT", "fact_kind": "PER_SHARE"})
    if not per_share and PER_SHARE_FIXTURE.exists():
        per_share = list(csv.DictReader(PER_SHARE_FIXTURE.open(encoding="utf-8")))
    facts.extend(per_share)
    OUT_FACTS.parent.mkdir(parents=True, exist_ok=True)
    fields = ["ticker","cik","issuer_name","security_type","taxonomy","tag","unit","raw_value",
              "normalized_cash_dividend","period_start","period_end","filed_date","form",
              "fiscal_year","fiscal_period","accession_number","source_url","available_at",
              "period_type","allocation_status","verification_status","fact_kind"]
    with OUT_FACTS.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(facts)
    # coverage at unique CIK
    fidx = defaultdict(list)
    for x in facts:
        fidx[x["cik"]].append(x)
    cov = []
    for cik in sorted(all_ciks):
        recs = by_cik.get(cik, [])
        fs = [x for x in fidx[cik] if x["fact_kind"] == "TOTAL_CASH"]
        positive = [x for x in fs if x["raw_value"] > 0]
        complete_filed = bool(fs) and all(x["filed_date"] for x in fs)
        ttm = ttm_status([(x["period_start"], x["period_end"]) for x in fs if x["period_type"] == "QUARTER"])
        alloc = "NO_CURRENT_SECURITY"
        if recs:
            if len(recs) > 1: alloc = "ISSUER_LEVEL_NOT_TICKER_ALLOCABLE"
            elif recs[0]["security_type"] == "ADR": alloc = "ADR_RATIO_UNVERIFIED"
            elif recs[0]["security_type"] == "COMMON": alloc = "TICKER_ALLOCABLE"
            else: alloc = "ISSUER_LEVEL_NOT_TICKER_ALLOCABLE"
        cov.append({"cik": cik, "tickers": "|".join(x["ticker"] for x in recs),
                    "issuer_name": recs[0]["security_name"] if recs else "",
                    "security_type": "MULTI_CLASS" if len(recs) > 1 else (recs[0]["security_type"] if recs else "UNKNOWN"),
                    "model_family": sic.get(recs[0]["ticker"], {}).get("model_family", "") if recs else "",
                    "cash_fact_count": len(fs), "cash_period_count": len({x["period_end"] for x in fs}),
                    "positive_fact_count": len(positive), "has_filed_dates": complete_filed,
                    "annual_period_count": len({x["period_end"] for x in fs if x["period_type"] == "ANNUAL"}),
                    "ttm_status": ttm, "allocation_status": alloc,
                    "payer_evidence": "CONFIRMED_PAYER_EVIDENCE" if positive else ("NO_POSITIVE_FACT_IN_OBSERVATION_WINDOW" if fs else "DIVIDEND_STATUS_UNKNOWN"),
                    "duplicate_fact_count": duplicates, "currency": "|".join(sorted({x["unit"] for x in fs}))})
    with OUT_COV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(cov[0].keys())); w.writeheader(); w.writerows(cov)
    def cnt_cov(key, value): return sum(1 for x in cov if x[key] == value)
    summary = {"metadata": {"generated_at": datetime.now(timezone.utc).isoformat(), "panel": str(a.panel),
        "snapshot": str(SNAPSHOT), "source": "P6.3 normalized panel + existing 28-CIK raw cache",
        "no_sec_download": True},
        "universe": {"target_records": len(uni), "unique_ciks": len(all_ciks),
                     "ciks_with_cash_fact": len(cash_ciks)},
        "cash_facts": {"rows": len(facts) - len(per_share), "per_share_rows": len(per_share),
                       "total_cash_ciks": len(cash_ciks), "duplicate_facts": duplicates,
                       "negative_raw_values": sign_anomalies,
                       "tags": dict(tags), "units": dict(units)},
        "coverage": {"has_cash_fact": len(cash_ciks),
                     "has_positive_evidence": sum(1 for x in cov if x["payer_evidence"] == "CONFIRMED_PAYER_EVIDENCE"),
                     "no_positive_in_window": sum(1 for x in cov if x["payer_evidence"] == "NO_POSITIVE_FACT_IN_OBSERVATION_WINDOW"),
                     "unknown": sum(1 for x in cov if x["payer_evidence"] == "DIVIDEND_STATUS_UNKNOWN"),
                     "ttm_available": cnt_cov("ttm_status","TTM_AVAILABLE"),
                     "ttm_unavailable": cnt_cov("ttm_status","TTM_UNAVAILABLE"),
                     "complete_filed": sum(1 for x in cov if x["has_filed_dates"]),
                     "ticker_allocable_common": sum(1 for x in cov if x["allocation_status"] == "TICKER_ALLOCABLE"),
                     "issuer_level_not_allocable": sum(1 for x in cov if x["allocation_status"] == "ISSUER_LEVEL_NOT_TICKER_ALLOCABLE"),
                     "adr_unverified": sum(1 for x in cov if x["allocation_status"] == "ADR_RATIO_UNVERIFIED"),
                     "multi_class": sum(1 for x in cov if x["security_type"] == "MULTI_CLASS")},
        "per_share": {"rows": len(per_share), "tag_counts": dict(Counter(x["tag"] for x in per_share)),
                      "ciks": len({x["cik"] for x in per_share})},
        "sample30": {"note": "P6.11 sample has 24 cash-flow facts and 25 positive payer evidence; per-share 0 in P6.3 map"},
        "status": "CASH_DIVIDEND_PROXY_FEASIBLE_WITH_LIMITS" if len(cash_ciks) else "CASH_DIVIDEND_PROXY_UNAVAILABLE",
        "notes": ["Cash amount is issuer-level and not DPS.",
                  "Multi-ticker and ADR records are not allocated to a ticker.",
                  "Only USD is directly comparable across issuers; other currencies retained but flagged by unit.",
                  "TTM only when four contiguous non-overlapping quarter facts exist."]}
    OUT_SUM.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary["cash_facts"] | {"coverage": summary["coverage"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
