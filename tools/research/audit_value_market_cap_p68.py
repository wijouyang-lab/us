"""P6.8 issuer market-cap audit and metric-level Value V1 readiness.

No external requests; uses P6.2/P6.3/P6.5 data and the P6.3 panel artifact.
"""
from __future__ import annotations
import argparse, csv, gzip, json, math
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

CURRENT = Path("data/universe/us_equities_current.csv")
QUOTES = Path("data/universe/us_market_quote_mapping_p62.csv")
READY = Path("data/universe/us_equity_quality_readiness_p65.csv")
SIC = Path("data/universe/us_equity_industry_sic_p65.csv")
PANEL = Path("data/universe/sec_fundamentals_panel_p63.csv.gz")
OUT_JSON = Path("data/universe/value_market_cap_audit_p68.json")
OUT_COV = Path("data/universe/value_metric_coverage_p68.csv")
OUT_READY = Path("data/universe/value_v1_readiness_p68.csv")
OUT_MAP = Path("data/universe/value_v1_metric_map_p68.json")
SNAPSHOT = date(2026, 11, 5)
SPECIAL = {"BANKS","INSURANCE","REIT","BDC","OTHER_FINANCIALS","UTILITIES","ENERGY","UNCLASSIFIED"}
STANDARD = {"TECHNOLOGY","INDUSTRIALS","HEALTHCARE","CONSUMER_DISCRETIONARY",
            "CONSUMER_STAPLES","COMMUNICATIONS","MATERIALS","OTHER_SERVICES"}
METRICS = ("NetIncome","StockholdersEquity","Revenue","OperatingCashFlow","CapitalExpenditure",
           "LongTermDebt","CashAndCashEquivalents","OperatingIncome","TotalAssets","CommonSharesOutstanding")


def num(v):
    try:
        x = float(v); return x if math.isfinite(x) else None
    except (TypeError, ValueError): return None


def dt(v):
    try: return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError): return None


def latest_by_end(recs):
    if not recs: return None
    recs = sorted(recs, key=lambda x: (x["end"], x["filed"] or date.min, x["accn"]))
    return recs[-1]


def load_fin(panel: Path, snapshot: date):
    annual = defaultdict(lambda: defaultdict(list))
    instant = defaultdict(lambda: defaultdict(list))
    with gzip.open(panel, "rt", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            m = r.get("metric")
            if m not in METRICS: continue
            if r.get("unit") not in (("shares",) if m == "CommonSharesOutstanding" else ("USD",)):
                continue
            pit = dt(r.get("pit_available_date")); end = dt(r.get("end"))
            if not pit or not end or pit > snapshot: continue
            cik = (r.get("cik") or "").zfill(10)
            rec = {"value": num(r.get("value")), "end": end, "filed": dt(r.get("filed")),
                   "accn": r.get("accn") or "", "period_type": r.get("period_type") or ""}
            if rec["value"] is None: continue
            if m in ("TotalAssets","StockholdersEquity","LongTermDebt","CashAndCashEquivalents","CommonSharesOutstanding"):
                instant[cik][m].append(rec)
            elif rec["period_type"] == "ANNUAL":
                annual[cik][m].append(rec)
    out = {}
    for cik in set(annual) | set(instant):
        a = {m: latest_by_end(v) for m, v in annual.get(cik, {}).items()}
        i = {m: latest_by_end(v) for m, v in instant.get(cik, {}).items()}
        out[cik] = {"annual": a, "instant": i}
    return out


def unit_ok(cap): return cap is not None and cap > 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", type=Path, default=PANEL)
    ap.add_argument("--json", type=Path, default=OUT_JSON)
    ap.add_argument("--coverage", type=Path, default=OUT_COV)
    ap.add_argument("--readiness", type=Path, default=OUT_READY)
    ap.add_argument("--map", type=Path, default=OUT_MAP)
    a = ap.parse_args()
    if not a.panel.exists(): print("P6.3 PANEL ARTIFACT MISSING"); return 2
    uni = list(csv.DictReader(CURRENT.open(encoding="utf-8")))
    quotes = {r["ticker"]: r for r in csv.DictReader(QUOTES.open(encoding="utf-8"))}
    ready = {r["ticker"]: r for r in csv.DictReader(READY.open(encoding="utf-8"))}
    sic = {r["ticker"]: r for r in csv.DictReader(SIC.open(encoding="utf-8"))}
    fin = load_fin(a.panel, SNAPSHOT)
    cik_tickers = defaultdict(list)
    for u in uni:
        c = (u.get("CIK") or "").strip().zfill(10)
        if c: cik_tickers[c].append(u["ticker"])
    rows = []
    for u in uni:
        t = u["ticker"]; cik = (u.get("CIK") or "").strip().zfill(10) if (u.get("CIK") or "").strip() else ""
        q = quotes.get(t, {}); rd = ready.get(t, {}); sd = sic.get(t, {})
        price = num(q.get("quote_price")); cap = num(q.get("market_cap_raw")); pe_provider = num(q.get("pe_raw"))
        family = sd.get("model_family") or "UNCLASSIFIED"
        special = family in SPECIAL
        shares = (fin.get(cik, {}).get("instant", {}).get("CommonSharesOutstanding") or {}).get("value")
        implied = cap / price if cap and price and price > 0 else None
        ratio = implied / shares if implied and shares and shares > 0 else None
        same_cik = cik_tickers.get(cik, [])
        caps_same_cik = [num(quotes.get(x, {}).get("market_cap_raw")) for x in same_cik]
        caps_same_cik = [x for x in caps_same_cik if x is not None]
        same_cap = bool(len(set(round(x,2) for x in caps_same_cik)) == 1) if caps_same_cik else False
        if not unit_ok(cap):
            mc_status = "MARKET_CAP_MISSING"
        elif u["security_type"] == "ADR":
            mc_status = "ADR_MARKET_CAP_UNVERIFIED"
        elif len(same_cik) > 1:
            mc_status = "SHARE_CLASS_MARKET_CAP_UNVERIFIED"
        elif shares is None:
            mc_status = "SHARE_CLASS_MARKET_CAP_UNVERIFIED"
        elif ratio is not None and 0.90 <= ratio <= 1.10:
            mc_status = "ISSUER_MARKET_CAP_VALIDATED"
        else:
            mc_status = "ISSUER_MARKET_CAP_CONFLICT"
        mc_valid = mc_status == "ISSUER_MARKET_CAP_VALIDATED"
        # financial latest values
        f = fin.get(cik, {}); an = f.get("annual", {}); ins = f.get("instant", {})
        ni = (an.get("NetIncome") or {}).get("value")
        eq = (ins.get("StockholdersEquity") or {}).get("value")
        rev = (an.get("Revenue") or {}).get("value")
        ocf = (an.get("OperatingCashFlow") or {}).get("value")
        capex = (an.get("CapitalExpenditure") or {}).get("value")
        debt = (ins.get("LongTermDebt") or {}).get("value")
        cash = (ins.get("CashAndCashEquivalents") or {}).get("value")
        opinc = (an.get("OperatingIncome") or {}).get("value")
        accounting = rd.get("accounting_standard") or "NONE"
        pe = cap / ni if mc_valid and ni is not None and ni > 0 and cap else None
        pb = cap / eq if mc_valid and eq is not None and eq > 0 and cap else None
        ps = cap / rev if mc_valid and rev is not None and rev > 0 and cap else None
        ey = ni / cap if mc_valid and ni is not None and cap and cap > 0 else None
        fcf = ocf - capex if ocf is not None and capex is not None else None
        fcfy = fcf / cap if mc_valid and fcf is not None and cap and cap > 0 else None
        pe_mismatch = None
        if pe is not None and pe_provider is not None and pe_provider != 0:
            pe_mismatch = abs(pe / pe_provider - 1)
        ev_ready = False; ev_reason = "EV_DATA_INCOMPLETE"
        # Depreciation/Amortization is not in the P6.3 metric map, so EV/EBITDA cannot be complete.
        metrics_ready = [x for x, v in (("PE", pe), ("PB", pb), ("PS", ps), ("EY", ey), ("FCFY", fcfy)) if v is not None]
        standard_ok = family in STANDARD
        no_conflict = mc_status in ("ISSUER_MARKET_CAP_VALIDATED",)
        if special:
            vstatus = "VALUE_SPECIAL_MODEL_REQUIRED"
        elif not mc_valid:
            vstatus = "VALUE_V1_BLOCKED"
        elif not standard_ok or accounting not in ("US_GAAP","IFRS"):
            vstatus = "VALUE_V1_BLOCKED"
        elif len(metrics_ready) >= 2:
            vstatus = "VALUE_V1_DATA_READY"
        else:
            vstatus = "VALUE_V1_BLOCKED"
        rows.append({"ticker": t, "cik": cik, "exchange": u["exchange"], "security_type": u["security_type"],
            "cohort": "TARGET" if u["security_type"] in ("COMMON","ADR") else "UNCLASSIFIED",
            "industry": family, "model_family": family, "special_model": special,
            "accounting_standard": accounting, "price": price, "market_cap_raw": cap,
            "implied_shares": implied, "sec_shares": shares, "shares_ratio": ratio,
            "cik_ticker_count": len(same_cik), "same_cik_same_cap": same_cap,
            "market_cap_status": mc_status, "market_cap_validated": mc_valid,
            "net_income": ni, "stockholders_equity": eq, "revenue": rev,
            "operating_cash_flow": ocf, "capital_expenditure": capex,
            "free_cash_flow": fcf, "long_term_debt": debt, "cash": cash,
            "pe_provider": pe_provider, "pe_derived": pe, "pe_reconciliation_ratio": (pe/pe_provider if pe and pe_provider else None),
            "pe_mismatch": pe_mismatch,
            "pb": pb, "ps": ps, "earnings_yield": ey, "fcf_yield": fcfy,
            "ev_ebitda": None, "ev_ebitda_status": ev_reason,
            "pe_ready": pe is not None, "pb_ready": pb is not None, "ps_ready": ps is not None,
            "earnings_yield_ready": ey is not None, "fcf_yield_ready": fcfy is not None,
            "ev_ebitda_ready": False,
            "metric_ready_count": len(metrics_ready),
            "value_v1_status": vstatus,
            "blocker_codes": "|".join(dict.fromkeys([
                ("MARKET_CAP_STATUS_" + mc_status) if not mc_valid else "",
                ("ACCOUNTING_" + accounting) if accounting not in ("US_GAAP","IFRS") else "",
                ("INDUSTRY_SPECIAL" if special else ""),
                ("INSUFFICIENT_VALUE_METRICS" if len(metrics_ready) < 2 else ""),
                "EV_EBITDA_DA_MISSING"]))
        })
    trows = [r for r in rows if r["cohort"] == "TARGET"]
    urows = [r for r in rows if r["cohort"] == "UNCLASSIFIED"]
    def cnt(rs, key): return sum(1 for r in rs if r[key])
    by_type = {}
    for typ in ("COMMON","ADR"):
        rs = [r for r in trows if r["security_type"] == typ]
        by_type[typ] = {"records": len(rs),
            "market_cap_present": cnt(rs,"market_cap_raw"),
            "market_cap_validated": cnt(rs,"market_cap_validated"),
            "value_data_ready": sum(1 for r in rs if r["value_v1_status"]=="VALUE_V1_DATA_READY")}
    by_exchange = {}
    for ex in sorted({r["exchange"] for r in trows}):
        rs = [r for r in trows if r["exchange"] == ex]
        by_exchange[ex] = {"records": len(rs), "market_cap_validated": cnt(rs,"market_cap_validated")}
    by_acc = {}
    for ac in sorted({r["accounting_standard"] for r in trows}):
        rs = [r for r in trows if r["accounting_standard"] == ac]
        by_acc[ac] = {"records": len(rs), "value_data_ready": sum(1 for r in rs if r["value_v1_status"]=="VALUE_V1_DATA_READY")}
    by_family = {}
    for fam in sorted({r["model_family"] for r in trows}):
        rs = [r for r in trows if r["model_family"] == fam]
        by_family[fam] = {"records": len(rs), "market_cap_validated": cnt(rs,"market_cap_validated"),
                          "value_data_ready": sum(1 for r in rs if r["value_v1_status"]=="VALUE_V1_DATA_READY")}
    a.readiness.parent.mkdir(parents=True, exist_ok=True)
    with a.readiness.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    # metric coverage per record and unique CIK
    unique = {}
    for r in trows:
        if r["cik"]: unique.setdefault(r["cik"], r)
    coverage = []
    for name, key in (("PE","pe_ready"),("PB","pb_ready"),("PS","ps_ready"),
                      ("EarningsYield","earnings_yield_ready"),("FCFYield","fcf_yield_ready"),
                      ("EV_EBITDA","ev_ebitda_ready")):
        coverage.append({"metric": name,
            "ticker_ready": cnt(trows,key), "ticker_coverage": round(cnt(trows,key)/len(trows),6),
            "cik_ready": sum(1 for r in unique.values() if r[key]),
            "cik_coverage": round(sum(1 for r in unique.values() if r[key])/len(unique),6) if unique else 0})
    with a.coverage.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(coverage[0].keys())); w.writeheader(); w.writerows(coverage)
    mc_counts = Counter(r["market_cap_status"] for r in trows)
    pe_mismatch = sum(1 for r in trows if r["pe_mismatch"] is not None and r["pe_mismatch"] > 0.2)
    audit = {"metadata": {"generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_date": str(SNAPSHOT), "panel": str(a.panel),
        "market_cap_source": "P6.2 quote_market_cap_raw",
        "note": "Market cap validated only when a single-ticker, non-ADR issuer's cap/price implied shares reconcile to SEC shares within 10%."},
        "pool": {"target_records": len(trows), "target_unique_ciks": len(unique),
                 "unclassified_records": len(urows)},
        "market_cap": {"present": sum(1 for r in trows if r["market_cap_raw"] is not None),
                       "validated": sum(1 for r in trows if r["market_cap_validated"]),
                       "status_counts": dict(mc_counts),
                       "multi_ticker_ciks": sum(1 for c, ts in cik_tickers.items() if len(ts)>1),
                       "multi_ticker_records": sum(1 for r in trows if r["cik_ticker_count"]>1),
                       "same_cik_same_cap_records": sum(1 for r in trows if r["cik_ticker_count"] > 1 and r["same_cik_same_cap"]),
                       "multi_ticker_same_cap_ciks": sum(1 for c, ts in cik_tickers.items() if len(ts) > 1 and len({round(num(quotes.get(x, {}).get("market_cap_raw")) or 0, 2) for x in ts}) == 1),
                       "share_class_unverified_records": mc_counts.get("SHARE_CLASS_MARKET_CAP_UNVERIFIED",0),
                       "adr_unverified_records": mc_counts.get("ADR_MARKET_CAP_UNVERIFIED",0),
                       "conflict_records": mc_counts.get("ISSUER_MARKET_CAP_CONFLICT",0)},
        "value_status_counts": dict(Counter(r["value_v1_status"] for r in trows)),
        "by_type": by_type, "by_exchange": by_exchange, "by_accounting": by_acc,
        "by_family": by_family, "metric_coverage": coverage,
        "pe_provider_mismatch_gt_20pct": pe_mismatch,
        "pe_comparable": sum(1 for r in trows if r["pe_derived"] is not None and r["pe_provider"] is not None),
        "ev_ebitda_ready": 0, "ev_ebitda_blocker": "DEPRECIATION_AMORTIZATION_NOT_IN_P63_METRIC_MAP",
        "unclassified": {"records": len(urows), "validated": sum(1 for r in urows if r["market_cap_validated"]),
                         "value_data_ready": sum(1 for r in urows if r["value_v1_status"]=="VALUE_V1_DATA_READY")},
        "notes": ["Market cap is not treated as issuer total for multi-ticker or ADR records.",
                  "Same CIK same market cap is evidence, not proof of issuer-total semantics.",
                  "EV/EBITDA remains unavailable because D&A is not in the P6.3 mapped panel.",
                  "No production Value score is produced."]}
    a.json.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    metric_map = {"metrics": {
        "PE": "market cap / positive net income; provider PE reconciled",
        "PB": "market cap / positive stockholders equity",
        "PS": "market cap / positive annual revenue",
        "EarningsYield": "net income / market cap, negative retained",
        "FCFYield": "(operating cash flow - capex) / market cap; capex missing => blocked",
        "EV_EBITDA": "EV = cap + debt - cash; EBITDA = operating income + D&A; D&A missing => blocked"},
        "applicability": {"BANKS":["PB"],"INSURANCE":["PB"],"REIT":["PB","PS"],
            "OTHER_FINANCIALS":["PB"],"STANDARD":["PE","PB","PS","EarningsYield","FCFYield"]},
        "status_model": ["MARKET_CAP_READY","PE_READY","PB_READY","PS_READY",
                         "EARNINGS_YIELD_READY","FCF_YIELD_READY","EV_EBITDA_READY",
                         "VALUE_V1_DATA_READY","VALUE_V1_BLOCKED","VALUE_SPECIAL_MODEL_REQUIRED"]}
    a.map.write_text(json.dumps(metric_map, indent=2), encoding="utf-8")
    print(json.dumps({"pool": audit["pool"], "market_cap": audit["market_cap"],
                      "value_status": audit["value_status_counts"], "type": by_type}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
