"""P6.4 six-style full-market data readiness audit.

No scores, no backtests, no network. Uses P6.1/P6.2 files and the P6.3 panel artifact.
"""
from __future__ import annotations
import argparse, csv, gzip, json
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

CURRENT = Path("data/universe/us_equities_current.csv")
QUOTE_MAP = Path("data/universe/us_market_quote_mapping_p62.csv")
QUOTE_JSON = Path("data/universe/us_market_quote_coverage_p62.json")
COV = Path("data/universe/sec_fundamentals_coverage_p63.csv")
AUDIT = Path("data/universe/sec_fundamentals_audit_p63.json")
PANEL = Path("data/universe/sec_fundamentals_panel_p63.csv.gz")
SP500 = Path("sp500_constituents.csv")
OUT_CSV = Path("data/universe/us_equity_style_readiness_p64.csv")
OUT_JSON = Path("data/universe/us_equity_style_coverage_p64.json")
OUT_METRIC = Path("data/universe/us_equity_style_metric_coverage_p64.csv")
OUT_IND = Path("data/universe/us_equity_industry_coverage_p64.csv")
SAMPLE_28 = {"AAPL","MSFT","GOOGL","NVDA","CRM","ADBE","AMZN","HD","MCD","NKE","CAT","HON","UNP","XOM","CVX","NEE","DUK","JNJ","PFE","UNH","MRNA","JPM","BAC","BRK.B","MET","PLD","O","RIVN"}
HISTORY_PASS_23 = {"AAPL","MSFT","GOOGL","CRM","ADBE","AMZN","MCD","NKE","CAT","UNP","XOM","CVX","DUK","JNJ","PFE","UNH","MRNA","BAC","MET","PLD","O","RIVN","BRK.B"}
STYLES = ("value","quality","garp","trend","dividend","hedge")
STATUSES = ("DATA_AVAILABLE","DATA_QUALITY_PASS","INPUT_READY")


def b(v) -> bool:
    return str(v).strip().lower() in ("true","1","yes","y")


def num(v):
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def norm_ticker(v: str) -> str:
    import re
    x = re.sub(r"[^A-Z0-9]", ".", str(v or "").upper())
    return re.sub(r"\.+", ".", x).strip(".")


def derive_quarter_from_ytd(current_ytd, prior_ytd):
    """Q2/Q3 YTD -> standalone quarter; never treat YTD as a quarter."""
    a, b_ = num(current_ytd), num(prior_ytd)
    if a is None or b_ is None: return None
    return a - b_


def industry_maps():
    sector = {}
    if SP500.exists():
        with SP500.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                sector[norm_ticker(r.get("Ticker",""))] = (r.get("Sector") or "").strip()
    return sector


def industry_group(ind: str) -> str:
    if not ind: return "INDUSTRY_CLASSIFICATION_MISSING"
    x = ind.lower()
    if "financial" in x: return "FINANCIALS"
    if "real estate" in x: return "REAL_ESTATE"
    if "utilit" in x: return "UTILITIES"
    if "energy" in x: return "ENERGY"
    return "STANDARD"


def classify_security(q, c, p, industry, historical_pass=False):
    """Pure classification used by tests and the production audit."""
    blockers = []
    tm = q.get("match_status")
    quote_ready = tm == "QUOTE_MATCHED" and (num(q.get("quote_price")) or 0) > 0
    if not quote_ready: blockers.append("QUOTE_" + (tm or "MISSING"))
    found = b(c.get("companyfacts_found")); std = b(c.get("standard_facts"))
    us = b(c.get("us_gaap_facts")); ifrs = b(c.get("ifrs_facts"))
    if not found: blockers.append("COMPANYFACTS_MISSING")
    if not std: blockers.append("STANDARD_TAXONOMY_MISSING")
    accounting = "MIXED" if us and ifrs else "US_GAAP" if us else "IFRS" if ifrs else "NONE"
    if accounting == "MIXED": blockers.append("MIXED_ACCOUNTING_STANDARDS")
    if accounting == "NONE": blockers.append("ACCOUNTING_STANDARD_MISSING")
    ind_group = industry_group(industry)
    if ind_group == "INDUSTRY_CLASSIFICATION_MISSING": blockers.append("INDUSTRY_CLASSIFICATION_MISSING")
    special = ind_group in ("FINANCIALS","REAL_ESTATE","UTILITIES","ENERGY")
    if special: blockers.append("SPECIAL_INDUSTRY_MODEL_REQUIRED")
    metrics = {m: b(c.get(m + "_any")) for m in (
        "Revenue","NetIncome","EPSBasic","EPSDiluted","TotalAssets","StockholdersEquity",
        "OperatingCashFlow","CapitalExpenditure","CashAndCashEquivalents","LongTermDebt",
        "CommonSharesOutstanding","DividendsPaid")}
    recent = {m: b(c.get(m + "_recent")) for m in metrics}
    ann = p.get("annual", {}) if p else {}
    mp = p.get("metric_period", {}) if p else {}
    ann_ok = (ann.get("NetIncome", 0) >= 2
              and mp.get("TotalAssets", {}).get("INSTANT", 0) >= 2
              and mp.get("StockholdersEquity", {}).get("INSTANT", 0) >= 2)
    hist_fin = found and std and accounting in ("US_GAAP","IFRS")
    # Value: availability is not input readiness without verified share class / ADR ratio / EV.
    value_available = quote_ready and found
    value_quality = value_available and std and num(q.get("market_cap_raw")) is not None and all(
        metrics[m] for m in ("Revenue","NetIncome","EPSBasic","TotalAssets","StockholdersEquity","OperatingCashFlow"))
    value_ready = False
    if not value_quality:
        blockers.append("VALUE_FIELDS_INCOMPLETE")
    blockers += ["VALUE_SHARE_CLASS_OR_ADR_RATIO_UNVERIFIED", "VALUE_EV_EBITDA_UNVERIFIED"]
    # Quality
    quality_avail = hist_fin and any(metrics[m] for m in ("NetIncome","TotalAssets","StockholdersEquity","Revenue","OperatingCashFlow"))
    quality_pass = quality_avail and ann_ok and metrics["Revenue"] and metrics["OperatingCashFlow"]
    quality_ready = quality_pass and ind_group not in ("INDUSTRY_CLASSIFICATION_MISSING","FINANCIALS","REAL_ESTATE","UTILITIES","ENERGY")
    if not quality_ready:
        if ind_group == "INDUSTRY_CLASSIFICATION_MISSING": blockers.append("QUALITY_INDUSTRY_MODEL_UNRESOLVED")
        elif special: blockers.append("QUALITY_SPECIAL_INDUSTRY_MODEL_NOT_READY")
        elif not ann_ok: blockers.append("QUALITY_HISTORY_INSUFFICIENT")
        else: blockers.append("QUALITY_FIELDS_INCOMPLETE")
    # GARP: historical growth only; forward EPS not in free source.
    garp_avail = hist_fin and (metrics["Revenue"] or metrics["EPSBasic"])
    garp_pass = garp_avail and ann.get("Revenue", 0) >= 2 and ann.get("EPSBasic", 0) >= 2
    garp_ready = False
    blockers.append("GARP_FORWARD_EPS_MISSING")
    if not garp_pass: blockers.append("GARP_HISTORICAL_GROWTH_INSUFFICIENT")
    # Trend
    trend_avail = quote_ready
    trend_pass = trend_avail and historical_pass
    trend_ready = False
    blockers += ["TREND_PIT_UNIVERSE_NOT_READY", "TREND_HISTORY_NOT_MARKET_WIDE"]
    # Dividend
    div_class = "CONFIRMED_DIVIDEND_PAYER" if metrics["DividendsPaid"] else "DIVIDEND_DATA_MISSING"
    div_avail = metrics["DividendsPaid"]
    div_quality = div_avail and recent["DividendsPaid"] and metrics["OperatingCashFlow"]
    div_ready = False
    if not div_avail: blockers.append("DIVIDEND_DATA_MISSING_NOT_NON_PAYER")
    elif not div_ready: blockers.append("DIVIDEND_DPS_FREQUENCY_ANNOUNCEMENT_MISSING")
    # Hedge: risk controls vs real options.
    risk_control = trend_pass
    options_hedge = False
    hedge_avail = quote_ready
    hedge_pass = risk_control
    hedge_ready = False
    blockers += ["OPTIONS_HISTORY_BORROW_FINANCING_MISSING"]
    return {
        "quote_ready": quote_ready, "historical_price_ready": bool(historical_pass),
        "companyfacts_found": found, "standard_facts": std, "accounting_standard": accounting,
        "industry": industry or "INDUSTRY_CLASSIFICATION_MISSING", "industry_group": ind_group,
        "special_industry": special,
        "value_status": "DATA_QUALITY_PASS" if value_quality else "DATA_AVAILABLE" if value_available else "DATA_MISSING",
        "value_input_ready": value_ready,
        "quality_status": "INPUT_READY" if quality_ready else "DATA_QUALITY_PASS" if quality_pass else "DATA_AVAILABLE" if quality_avail else "DATA_MISSING",
        "garp_status": "DATA_QUALITY_PASS" if garp_pass else "DATA_AVAILABLE" if garp_avail else "DATA_MISSING",
        "historical_growth_ready": bool(garp_pass), "forward_growth_ready": False,
        "trend_status": "DATA_QUALITY_PASS" if trend_pass else "DATA_AVAILABLE" if trend_avail else "DATA_MISSING",
        "current_quote_ready": quote_ready, "pit_universe_ready": False, "trend_backtest_ready": False,
        "dividend_status": "DATA_QUALITY_PASS" if div_quality else "DATA_AVAILABLE" if div_avail else "DIVIDEND_DATA_MISSING",
        "dividend_class": div_class, "dividend_input_ready": False,
        "hedge_status": "DATA_QUALITY_PASS" if hedge_pass else "DATA_AVAILABLE" if hedge_avail else "DATA_MISSING",
        "risk_control_input_ready": risk_control, "options_hedge_input_ready": options_hedge,
        "score_ready": False, "backtest_ready": False,
        "blocker_codes": "|".join(dict.fromkeys(blockers)),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", type=Path, default=PANEL)
    ap.add_argument("--out-csv", type=Path, default=OUT_CSV)
    ap.add_argument("--out-json", type=Path, default=OUT_JSON)
    ap.add_argument("--out-metric", type=Path, default=OUT_METRIC)
    ap.add_argument("--out-industry", type=Path, default=OUT_IND)
    a = ap.parse_args()
    if not a.panel.exists():
        print("P6.3 PANEL ARTIFACT MISSING: refusing to substitute sampled data")
        return 2
    with CURRENT.open(encoding="utf-8") as f: uni = list(csv.DictReader(f))
    with QUOTE_MAP.open(encoding="utf-8") as f: quotes = {r["ticker"]: r for r in csv.DictReader(f)}
    with COV.open(encoding="utf-8") as f: covs = {r["ticker"]: r for r in csv.DictReader(f)}
    sectors = industry_maps()
    # panel stats keyed by CIK; shared across tickers
    stats = defaultdict(lambda: {"annual": Counter(), "period": Counter(), "metric_period": defaultdict(Counter), "latest": "", "rows": 0})
    with gzip.open(a.panel, "rt", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            cik = (r.get("cik") or "").zfill(10)
            s = stats[cik]; s["rows"] += 1
            s["period"][r["period_type"]] += 1
            s["metric_period"][r["metric"]][r["period_type"]] += 1
            if r["period_type"] == "ANNUAL" and r.get("end"):
                s["annual"][r["metric"]] += 1
            s["latest"] = max(s["latest"], r.get("filed") or "")
    rows = []
    for u in uni:
        ticker = u["ticker"]
        cik = (u.get("CIK") or "").strip().zfill(10) if (u.get("CIK") or "").strip() else ""
        q = quotes.get(ticker, {})
        c = covs.get(ticker, {})
        ind = sectors.get(norm_ticker(ticker), "")
        p = stats.get(cik) if cik else None
        cls = classify_security(q, c, p, ind, ticker in HISTORY_PASS_23 and ticker in SAMPLE_28)
        row = {"ticker": ticker, "cik": cik if u.get("CIK") else "", "exchange": u["exchange"],
               "security_type": u["security_type"], "accounting_standard": cls["accounting_standard"],
               "industry": cls["industry"], "industry_group": cls["industry_group"],
               "special_industry": cls["special_industry"],
               "value_status": cls["value_status"], "quality_status": cls["quality_status"],
               "garp_status": cls["garp_status"], "trend_status": cls["trend_status"],
               "dividend_status": cls["dividend_status"], "hedge_status": cls["hedge_status"],
               "value_input_ready": cls["value_input_ready"], "quality_input_ready": cls["quality_status"] == "INPUT_READY",
               "garp_historical_growth_ready": cls["historical_growth_ready"],
               "garp_forward_growth_ready": cls["forward_growth_ready"],
               "trend_current_quote_ready": cls["current_quote_ready"],
               "trend_historical_price_ready": cls["historical_price_ready"],
               "trend_pit_universe_ready": cls["pit_universe_ready"],
               "trend_backtest_ready": cls["trend_backtest_ready"],
               "dividend_class": cls["dividend_class"], "dividend_input_ready": cls["dividend_input_ready"],
               "hedge_risk_control_input_ready": cls["risk_control_input_ready"],
               "hedge_options_input_ready": cls["options_hedge_input_ready"],
               "score_ready": False, "backtest_ready": False,
               "blocker_codes": cls["blocker_codes"],
               "data_as_of": c.get("latest_filed") or ""}
        if u["security_type"] == "UNCLASSIFIED":
            # Keep the row auditable, but never let an unclassified security
            # enter a confirmed Common/ADR model as INPUT_READY.
            row["quality_input_ready"] = False
            if row["quality_status"] == "INPUT_READY":
                row["quality_status"] = "DATA_QUALITY_PASS"
            row["value_input_ready"] = False
            row["garp_historical_growth_ready"] = False
            row["garp_forward_growth_ready"] = False
            row["dividend_input_ready"] = False
            row["hedge_risk_control_input_ready"] = False
            row["blocker_codes"] += "|UNCLASSIFIED_SECURITY_NOT_IN_COMMON_MODEL"
        rows.append(row)
    # main denominator excludes UNCLASSIFIED
    trows = [r for r in rows if r["security_type"] in ("COMMON","ADR")]
    urows = [r for r in rows if r["security_type"] == "UNCLASSIFIED"]
    def counts(rs):
        out = {}
        for style in STYLES:
            key = style + "_status"
            out[style] = {s: sum(1 for x in rs if x[key] == s) for s in STATUSES}
            out[style]["SCORE_READY"] = 0
            out[style]["BACKTEST_READY"] = 0
        return out
    status_counts = counts(trows)
    unclass_counts = counts(urows)
    by_type = {}
    for typ in ("COMMON","ADR"):
        rs = [r for r in trows if r["security_type"] == typ]
        by_type[typ] = {"records": len(rs), **{style: sum(1 for r in rs if r[style+"_status"]=="INPUT_READY") for style in STYLES}}
    by_exchange = {}
    for ex in sorted({r["exchange"] for r in trows}):
        rs = [r for r in trows if r["exchange"] == ex]
        by_exchange[ex] = {"records": len(rs), **{style: sum(1 for r in rs if r[style+"_status"]=="INPUT_READY") for style in STYLES}}
    by_accounting = {}
    for ac in sorted({r["accounting_standard"] for r in trows}):
        rs = [r for r in trows if r["accounting_standard"] == ac]
        by_accounting[ac] = {"records": len(rs), **{style: sum(1 for r in rs if r[style+"_status"]=="INPUT_READY") for style in STYLES}}
    blocker_counts = Counter()
    for r in trows:
        for bcode in r["blocker_codes"].split("|"):
            if bcode: blocker_counts[bcode] += 1
    # metric coverage from P6.3 columns
    metric_rows = []
    for m in ("Revenue","NetIncome","EPSBasic","TotalAssets","StockholdersEquity","OperatingCashFlow",
              "CapitalExpenditure","CashAndCashEquivalents","LongTermDebt","CommonSharesOutstanding","DividendsPaid"):
        any_n = sum(1 for r in trows if b(covs.get(r["ticker"],{}).get(m+"_any")))
        recent_n = sum(1 for r in trows if b(covs.get(r["ticker"],{}).get(m+"_recent")))
        metric_rows.append({"metric": m, "target_records": len(trows), "any": any_n,
                            "any_coverage": round(any_n/len(trows),6),
                            "recent_12m": recent_n, "recent_coverage": round(recent_n/len(trows),6)})
    # industry coverage
    ind_rows = []
    for ind in sorted({r["industry"] for r in rows}):
        rs = [r for r in trows if r["industry"] == ind]
        if not rs and ind == "INDUSTRY_CLASSIFICATION_MISSING": rs = [r for r in trows if r["industry"] == ind]
        if not rs: continue
        ind_rows.append({"industry": ind, "records": len(rs),
                         "quote_ready": sum(1 for r in rs if r["trend_current_quote_ready"]),
                         "companyfacts_found": sum(1 for r in rs if covs.get(r["ticker"],{}).get("companyfacts_found") == "True"),
                         "quality_input_ready": sum(1 for r in rs if r["quality_input_ready"]),
                         "special_industry": sum(1 for r in rs if r["special_industry"])})
    a.out_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else ["ticker"]
    with a.out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    with a.out_metric.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(metric_rows[0].keys())); w.writeheader(); w.writerows(metric_rows)
    with a.out_industry.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(ind_rows[0].keys())); w.writeheader(); w.writerows(ind_rows)
    report = {
        "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(),
                     "scope": "P6.1 current Common+ADR; UNCLASSIFIED separate",
                     "panel": str(a.panel), "panel_required": True,
                     "pit_rule": "filed -> next weekday; no holiday adjustment; no acceptanceDateTime",
                     "note": "Statuses are data-readiness only; no scores or backtests."},
        "counts": {"target_records": len(trows), "unclassified_records": len(urows),
                   "target_unique_ciks": len({r["cik"] for r in trows if r["cik"]}),
                   "target_unique_tickers": len({r["ticker"] for r in trows}),
                   "target_missing_cik": sum(1 for r in trows if not r["cik"])},
        "status_counts": status_counts,
        "unclassified_status_counts": unclass_counts,
        "by_type": by_type, "by_exchange": by_exchange, "by_accounting": by_accounting,
        "top_blockers": blocker_counts.most_common(30),
        "special_industry_records": sum(1 for r in trows if r["special_industry"]),
        "industry_classification_missing": sum(1 for r in trows if r["industry"] == "INDUSTRY_CLASSIFICATION_MISSING"),
        "metric_coverage": metric_rows,
        "industry_coverage": ind_rows,
        "score_ready": 0, "backtest_ready": 0,
        "notes": ["Value INPUT_READY is zero because market-wide share-class/ADR ratio and EV/EBITDA are unverified.",
                  "GARP forward growth is zero because no free forward EPS source is available.",
                  "Trend current quote is not historical PIT or backtest readiness.",
                  "Dividend missing is not a confirmed non-payer.",
                  "Hedge risk-control data is separate from historical options chains."]
    }
    a.out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"counts": report["counts"], "status_counts": status_counts,
                      "top_blockers": report["top_blockers"][:8]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
