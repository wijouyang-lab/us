"""P6.11 audit of free US dividend-event source availability.

The pinned AkShare version is inspected first. If no US dividend-event endpoint
exists, the 30-security sample is still selected and SEC cash-flow evidence is
cross-checked without making any network request.
"""
from __future__ import annotations
import sys
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parents[2]))
import argparse, csv, inspect, json, math
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

import akshare as ak

from tools.research.normalize_us_dividend_events_p611 import write_events, FIELDS

CURRENT = Path("data/universe/us_equities_current.csv")
COV = Path("data/universe/sec_fundamentals_coverage_p63.csv")
QUOTES = Path("data/universe/us_market_quote_mapping_p62.csv")
SIC = Path("data/universe/us_equity_industry_sic_p65.csv")
PANEL = Path("data/universe/sec_fundamentals_panel_p63.csv.gz")
MAP = Path("data/universe/sec_fundamentals_metric_map_p63.json")
OUT_SAMPLE = Path("data/universe/us_dividend_source_sample_p611.json")
OUT_EVENTS = Path("data/universe/us_dividend_events_sample_p611.csv")
OUT_SEC = Path("data/universe/us_dividend_sec_reconciliation_p611.csv")

A = ["CAT","KO","PG","XOM","O","NEE","VZ","MCD","HD","IBM","CSCO","F","PEP","WMT","T","LOW","INTC","PLD"]
B = ["BAC","JNJ","DUK","AAL","AURE","BBGI"]
C = ["ABNB","ACAD","AAOI"]
D = ["ASML","BZ","ATAT"]


def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except (TypeError, ValueError): return None


def latest_dividends_paid(panel: Path):
    best = {}
    with __import__("gzip").open(panel, "rt", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("metric") != "DividendsPaid" or r.get("unit") != "USD": continue
            cik=(r.get("cik") or "").zfill(10); filed=r.get("filed") or ""; end=r.get("end") or ""
            try: d=date.fromisoformat(filed[:10])
            except ValueError: continue
            if d > date(2026,11,5): continue
            if cik not in best or (end,filed) > (best[cik][0],best[cik][1]):
                best[cik]=(end,filed,num(r.get("value")),r.get("accn") or "")
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", type=Path, default=PANEL)
    a = ap.parse_args()
    uni = {r["ticker"]: r for r in csv.DictReader(CURRENT.open(encoding="utf-8"))}
    cov = {r["ticker"]: r for r in csv.DictReader(COV.open(encoding="utf-8"))}
    quotes = {r["ticker"]: r for r in csv.DictReader(QUOTES.open(encoding="utf-8"))}
    sic = {r["ticker"]: r for r in csv.DictReader(SIC.open(encoding="utf-8"))}
    dp = latest_dividends_paid(a.panel) if a.panel.exists() else {}
    groups = [("A","recent_sec_cashflow_payer",A),("B","historical_or_unclear_payer",B),
              ("C","no_sec_dividend_fact",C),("D","ADR_ratio_unverified",D)]
    selected = []
    for code, reason, tickers in groups:
        for t in tickers:
            u=uni.get(t)
            if not u: continue
            cik=(u.get("CIK") or "").zfill(10)
            selected.append({"ticker":t,"cik":cik,"security_type":u["security_type"],
                             "exchange":u["exchange"],"model_family":sic.get(t,{}).get("model_family","UNCLASSIFIED"),
                             "market_cap":quotes.get(t,{}).get("market_cap_raw",""),
                             "group":code,"selection_reason":reason,
                             "sec_dividends_paid_any":cov.get(t,{}).get("DividendsPaid_any",""),
                             "sec_dividends_paid_recent":cov.get(t,{}).get("DividendsPaid_recent",""),
                             "sec_latest_filed":cov.get(t,{}).get("latest_filed",""),
                             "sec_dividends_paid_value":dp.get(cik,(None,None,None,None))[2],
                             "sec_dividends_paid_period":dp.get(cik,(None,None,None,None))[0],
                             "sec_dividends_paid_filed":dp.get(cik,(None,None,None,None))[1],
                             "sec_dividends_paid_accn":dp.get(cik,(None,None,None,None))[3]})
    # capability audit
    cap = {"akshare_version": getattr(ak,"__version__","unknown"),
           "has_stock_us_dividend_payout": hasattr(ak,"stock_us_dividend_payout"),
           "has_stock_us_financial_indicator": hasattr(ak,"stock_us_financial_indicator"),
           "candidate_functions": [n for n in dir(ak) if "dividend" in n.lower()],
           "alternative_us_indicator": hasattr(ak,"stock_financial_us_analysis_indicator_em"),
           "source_status": "SOURCE_UNAVAILABLE" if not hasattr(ak,"stock_us_dividend_payout") else "AVAILABLE",
           "upstream": "Eastmoney / SECURITIES financial indicators for the alternative; no US dividend-event endpoint in pinned AkShare" if not hasattr(ak,"stock_us_dividend_payout") else "AkShare US dividend endpoint",
           "contract": "stock_us_dividend_payout(symbol=...) -> DataFrame" if hasattr(ak,"stock_us_dividend_payout") else None,
           "alternative_contract": None}
    if cap["alternative_us_indicator"]:
        try:
            cap["alternative_contract"] = str(inspect.signature(ak.stock_financial_us_analysis_indicator_em))
            src = inspect.getsource(ak.stock_financial_us_analysis_indicator_em)
            cap["alternative_has_payout_ratio"] = "PAYOUT_RATIO" in src
            cap["alternative_has_dps_or_event_dates"] = any(x in src for x in
                ("DIVIDEND_PER_SHARE","DIVIDENDS_PER_SHARE","EX_DIVIDEND","PAYMENT_DATE","RECORD_DATE"))
            cap["alternative_upstream"] = "https://datacenter.eastmoney.com/securities/api/data/v1/get RPT_USF10_FN_GMAININDICATOR"
        except Exception as e:
            cap["alternative_error"] = str(e)[:200]
    # SEC metric map check
    mm = json.loads(MAP.read_text(encoding="utf-8"))
    dps_tags = [tag for taxmap in mm.values() for tags in taxmap.values() for tag in tags
                if "Dividend" in tag and "PerShare" in tag]
    cap["sec_per_share_tags_in_map"] = dps_tags
    # empty event output and SEC reconciliation
    write_events(OUT_EVENTS, [])
    sec_rows=[]
    for s in selected:
        sec_rows.append({"ticker":s["ticker"],"cik":s["cik"],"security_type":s["security_type"],
            "sec_dividends_paid_value":s["sec_dividends_paid_value"],
            "sec_dividends_paid_period":s["sec_dividends_paid_period"],
            "sec_dividends_paid_filed":s["sec_dividends_paid_filed"],
            "sec_dividends_paid_accn":s["sec_dividends_paid_accn"],
            "sec_per_share_dividend_fact":"NOT_IN_P63_METRIC_MAP" if not dps_tags else "CHECK",
            "vendor_dps":"","vendor_ex_date":"","vendor_payment_date":"",
            "cross_check_status":"SEC_CASHFLOW_ONLY" if s["sec_dividends_paid_value"] is not None else "NO_SEC_CASHFLOW_FACT",
            "note":"DividendsPaid is total cash paid, not DPS; vendor event source unavailable."})
    with OUT_SEC.open("w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(sec_rows[0].keys())); w.writeheader(); w.writerows(sec_rows)
    status_counts = Counter("SOURCE_UNAVAILABLE" for _ in selected)
    sample = {"metadata":{"generated_at":datetime.now(timezone.utc).isoformat(),
        "sample_size":len(selected),"max_sample":30,"request_count":0,
        "no_external_request":True,"note":"No 30-request dividend pull was attempted because the pinned AkShare has no US dividend-event endpoint."},
        "source_audit":cap,
        "sample":[{"ticker":s["ticker"],"cik":s["cik"],"security_type":s["security_type"],
                   "group":s["group"],"selection_reason":s["selection_reason"]} for s in selected],
        "groups":{g:sum(1 for s in selected if s["group"]==g) for g in ("A","B","C","D")},
        "event_status_counts":dict(status_counts),
        "field_stats":{"dps_present":0,"announcement_date_present":0,"ex_date_present":0,
                       "record_date_present":0,"payment_date_present":0,"currency_present":0,
                       "duplicate_events":0},
        "sec_evidence":{"cashflow_fact_present":sum(1 for s in selected if s["sec_dividends_paid_value"] is not None),
                        "per_share_fact_present":0,"per_share_tag_in_map":dps_tags,
                        "payer_evidence":sum(1 for s in selected if s["sec_dividends_paid_any"]=="True")},
        "confirmed":{"CONFIRMED_DIVIDEND_PAYER":sum(1 for s in selected if s["sec_dividends_paid_any"]=="True"),
                     "CONFIRMED_NON_PAYER":0,"DIVIDEND_STATUS_UNKNOWN":len(selected)},
        "source_url":None,"raw_response":None,
        "status_counts":status_counts}
    OUT_SAMPLE.write_text(json.dumps(sample,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"capability":cap,"sample":len(selected),"groups":sample["groups"],
                      "sec":sample["sec_evidence"],"status":sample["confirmed"]},indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
