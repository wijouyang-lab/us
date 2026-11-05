"""P6.12 30-name validation of free US dividend sources.

Sources: SmarterDividends free API, Yahoo Finance dividends, Nasdaq Dividend
History. One attempt per ticker/source; stop a source on HTTP 429.
"""
from __future__ import annotations
import sys
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parents[2]))
import argparse, csv, hashlib, json, os, time, tempfile
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
import requests

from tools.research.normalize_dividend_sources_p612 import FIELDS, standard_event

SAMPLE = Path("data/universe/us_dividend_source_sample_p611.json")
SECREC = Path("data/universe/us_dividend_sec_reconciliation_p611.csv")
CURRENT = Path("data/universe/us_equities_current.csv")
OUT_RESULT = Path("data/universe/dividend_alternative_source_results_p612.json")
OUT_EVENTS = Path("data/universe/dividend_alternative_events_p612.csv")
OUT_COMP = Path("data/universe/dividend_source_comparison_p612.csv")
RAW = Path("data/research/dividend_alt_raw_p612")
SNAPSHOT = date(2026, 11, 6)
UA = "research-dividend-audit/1.0 (contact: project-owner)"


def load_sample():
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    return d["sample"]


def current_exchange():
    return {r["ticker"]: r for r in csv.DictReader(CURRENT.open(encoding="utf-8"))}


def raw_write(name, payload):
    RAW.mkdir(parents=True, exist_ok=True)
    p = RAW / (name + ".json")
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return hashlib.sha256(p.read_bytes()).hexdigest()


def smarter(t, rec):
    url = f"https://smarterdividends.com/api/v1/stocks/{t}"
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=30)
        status = r.status_code
        if status == 429: return {"status": 429, "error": "HTTP_429_STOP", "url": url}, None
        if status != 200: return {"status": status, "error": f"HTTP_{status}", "url": url}, None
        j = r.json()
        h = raw_write("smarter_" + t, j)
        div = j.get("dividend") or {}
        last = div.get("last_payment") or {}
        events = []
        if last:
            events.append(standard_event(ticker=t, cik=rec["cik"], security_type=rec["security_type"],
                source="SMARTERDIVIDENDS", source_symbol=j.get("symbol", t),
                ex_dividend_date=last.get("ex_date", ""), payment_date=last.get("pay_date", ""),
                dps=last.get("amount"), currency=j.get("currency", ""),
                dividend_type="REGULAR_CASH", frequency=div.get("frequency", ""),
                source_url=j.get("url") or "https://smarterdividends.com/dividend-api",
                as_of=j.get("as_of", ""), retrieved_at=datetime.now(timezone.utc).isoformat(),
                raw_payload=last, provider_event_kind="LAST_PAYMENT", split_adjustment="UNKNOWN",
                adr_ratio_verified=False))
        return {"status": status, "url": url, "as_of": j.get("as_of", ""),
                "name": j.get("name", ""), "matched": bool(j.get("symbol", "").upper() == t.upper()),
                "profile": div, "changes": j.get("changes") or [], "events": events,
                "raw_sha256": h, "currency": j.get("currency", ""),
                "attribution": j.get("url") or "https://smarterdividends.com/dividend-api"}, events
    except Exception as e:
        return {"status": None, "error": f"{type(e).__name__}: {str(e)[:200]}", "url": url}, None


def yahoo(t, rec):
    import yfinance as yf
    yf.set_tz_cache_location(tempfile.mkdtemp(prefix="yf-cache-"))
    url = f"https://finance.yahoo.com/quote/{t}/history?filter=div"
    try:
        ser = yf.Ticker(t).dividends
        if ser is None or len(ser) == 0:
            return {"status": 200, "url": url, "events": [], "error": None, "raw_sha256": None}, []
        raw = [{"date": str(i)[:10], "amount": float(v)} for i, v in ser.items()]
        h = raw_write("yahoo_" + t, raw)
        events = [standard_event(ticker=t, cik=rec["cik"], security_type=rec["security_type"],
            source="YAHOO_FINANCE", source_symbol=t, ex_dividend_date=x["date"],
            dps=x["amount"], currency="", dividend_type="UNKNOWN", frequency="",
            source_url=url, as_of=str(SNAPSHOT), retrieved_at=datetime.now(timezone.utc).isoformat(),
            raw_payload=x, provider_event_kind="EX_DATE_DIVIDEND_HISTORY",
            split_adjustment="YAHOO_SPLIT_ADJUSTED_HISTORY", adr_ratio_verified=False) for x in raw]
        return {"status": 200, "url": url, "events": events, "raw_sha256": h,
                "history_length": len(events), "currency": "", "error": None}, events
    except Exception as e:
        msg = str(e)
        code = 429 if "429" in msg or "Too Many Requests" in msg else None
        return {"status": code, "url": url, "events": [], "error": f"{type(e).__name__}: {msg[:300]}"}, []


def nasdaq(t, rec):
    url = f"https://api.nasdaq.com/api/quote/{t}/dividends?assetclass=stocks"
    try:
        r = requests.get(url, headers={"Accept": "application/json", "User-Agent": UA}, timeout=30)
        if r.status_code == 429: return {"status": 429, "error": "HTTP_429_STOP", "url": url}, []
        if r.status_code != 200: return {"status": r.status_code, "error": f"HTTP_{r.status_code}", "url": url}, []
        j = r.json(); h = raw_write("nasdaq_" + t, j)
        data = j.get("data") or {}
        if data.get("message") or not (data.get("dividends") or {}).get("rows"):
            return {"status": 200, "url": url, "events": [], "error": data.get("message") or "NO_ROWS",
                    "raw_sha256": h, "as_of": data.get("dividends", {}).get("asOf")}, []
        rows = (data.get("dividends") or {}).get("rows") or []
        events = []
        for row in rows:
            typ = (row.get("type") or "").strip().upper()
            etype = "SPECIAL_CASH" if "SPECIAL" in typ else "REGULAR_CASH" if "CASH" in typ else "OTHER"
            events.append(standard_event(ticker=t, cik=rec["cik"], security_type=rec["security_type"],
                source="NASDAQ_DIVIDEND_HISTORY", source_symbol=t,
                announcement_date=row.get("declarationDate", ""), ex_dividend_date=row.get("exOrEffDate", ""),
                record_date=row.get("recordDate", ""), payment_date=row.get("paymentDate", ""),
                dps=(row.get("amount") or "").replace("$", "").strip(), currency=row.get("currency", ""),
                dividend_type=etype, frequency="", source_url="https://www.nasdaq.com/market-activity/stocks/" + t + "/dividend-history",
                as_of=str(SNAPSHOT), retrieved_at=datetime.now(timezone.utc).isoformat(),
                raw_payload=row, provider_event_kind="NASDAQ_FULL_DIVIDEND_ROW",
                split_adjustment="NOT_SPLIT_ADJUSTED_PER_NASDAQ", adr_ratio_verified=False))
        return {"status": 200, "url": url, "events": events, "raw_sha256": h,
                "as_of": data.get("dividends", {}).get("asOf"), "error": None}, events
    except Exception as e:
        msg = str(e); code = 429 if "429" in msg or "Too Many Requests" in msg else None
        return {"status": code, "url": url, "events": [], "error": f"{type(e).__name__}: {msg[:300]}"}, []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smarter", action="store_true", default=True)
    a = ap.parse_args()
    sample = load_sample()
    exch = current_exchange()
    sec = {r["ticker"]: r for r in csv.DictReader(SECREC.open(encoding="utf-8"))}
    results = {}; events = []; comp = []
    source_meta = {"SMARTERDIVIDENDS": {"attempted": 0, "stopped_429": False},
                   "YAHOO_FINANCE": {"attempted": 0, "stopped_429": False},
                   "NASDAQ_DIVIDEND_HISTORY": {"attempted": 0, "stopped_429": False}}
    # Smarter
    for s in sample:
        t = s["ticker"]
        if source_meta["SMARTERDIVIDENDS"]["stopped_429"]: break
        source_meta["SMARTERDIVIDENDS"]["attempted"] += 1
        r, ev = smarter(t, s)
        results.setdefault(t, {})["SMARTERDIVIDENDS"] = r
        events.extend(ev or [])
        if r.get("status") == 429: source_meta["SMARTERDIVIDENDS"]["stopped_429"] = True
        comp.append({"ticker": t, "source": "SMARTERDIVIDENDS", "http_status": r.get("status"),
                     "success": bool(ev), "has_events": bool(ev), "event_count": len(ev or []),
                     "dps_count": sum(1 for x in ev or [] if x["dps"] != ""),
                     "ex_date_count": sum(1 for x in ev or [] if x["ex_dividend_date"]),
                     "payment_date_count": sum(1 for x in ev or [] if x["payment_date"]),
                     "declaration_date_count": sum(1 for x in ev or [] if x["announcement_date"]),
                     "record_date_count": sum(1 for x in ev or [] if x["record_date"]),
                     "currency_count": sum(1 for x in ev or [] if x["currency"]),
                     "match_status": "MATCHED" if r.get("matched") else "UNMATCHED",
                     "source_url": r.get("url"), "as_of": r.get("as_of"), "raw_sha256": r.get("raw_sha256"),
                     "error": r.get("error"), "sec_cash_paid": sec.get(t, {}).get("sec_dividends_paid_value", "")})
        time.sleep(1.05)
    # Yahoo
    for s in sample:
        t = s["ticker"]
        if source_meta["YAHOO_FINANCE"]["stopped_429"]: break
        source_meta["YAHOO_FINANCE"]["attempted"] += 1
        r, ev = yahoo(t, s)
        results.setdefault(t, {})["YAHOO_FINANCE"] = r
        events.extend(ev or [])
        if r.get("status") == 429: source_meta["YAHOO_FINANCE"]["stopped_429"] = True
        comp.append({"ticker": t, "source": "YAHOO_FINANCE", "http_status": r.get("status"),
                     "success": bool(ev), "has_events": bool(ev), "event_count": len(ev or []),
                     "dps_count": sum(1 for x in ev or [] if x["dps"] != ""),
                     "ex_date_count": sum(1 for x in ev or [] if x["ex_dividend_date"]),
                     "payment_date_count": 0, "declaration_date_count": 0, "record_date_count": 0,
                     "currency_count": 0, "match_status": "MATCHED" if ev else "UNKNOWN",
                     "source_url": r.get("url"), "as_of": r.get("as_of"), "raw_sha256": r.get("raw_sha256"),
                     "error": r.get("error"), "sec_cash_paid": sec.get(t, {}).get("sec_dividends_paid_value", "")})
        time.sleep(1.05)
    # Nasdaq only Nasdaq-listed sample
    for s in sample:
        t = s["ticker"]
        ex = exch.get(t, {}).get("exchange", "")
        if ex != "NASDAQ": continue
        if source_meta["NASDAQ_DIVIDEND_HISTORY"]["stopped_429"]: break
        source_meta["NASDAQ_DIVIDEND_HISTORY"]["attempted"] += 1
        r, ev = nasdaq(t, s)
        results.setdefault(t, {})["NASDAQ_DIVIDEND_HISTORY"] = r
        events.extend(ev or [])
        if r.get("status") == 429: source_meta["NASDAQ_DIVIDEND_HISTORY"]["stopped_429"] = True
        comp.append({"ticker": t, "source": "NASDAQ_DIVIDEND_HISTORY", "http_status": r.get("status"),
                     "success": bool(ev), "has_events": bool(ev), "event_count": len(ev or []),
                     "dps_count": sum(1 for x in ev or [] if x["dps"] != ""),
                     "ex_date_count": sum(1 for x in ev or [] if x["ex_dividend_date"]),
                     "payment_date_count": sum(1 for x in ev or [] if x["payment_date"]),
                     "declaration_date_count": sum(1 for x in ev or [] if x["announcement_date"]),
                     "record_date_count": sum(1 for x in ev or [] if x["record_date"]),
                     "currency_count": sum(1 for x in ev or [] if x["currency"]),
                     "match_status": "MATCHED", "source_url": r.get("url"), "as_of": r.get("as_of"),
                     "raw_sha256": r.get("raw_sha256"), "error": r.get("error"),
                     "sec_cash_paid": sec.get(t, {}).get("sec_dividends_paid_value", "")})
        time.sleep(1.05)
    # comparison CSV: add SEC evidence per row
    fields = ["ticker","source","http_status","success","has_events","event_count","dps_count",
              "ex_date_count","payment_date_count","declaration_date_count","record_date_count",
              "currency_count","match_status","source_url","as_of","raw_sha256","error","sec_cash_paid"]
    OUT_EVENTS.parent.mkdir(parents=True, exist_ok=True)
    with OUT_EVENTS.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(events)
    with OUT_COMP.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(comp)
    # summary capabilities
    def cap(source):
        rs = [c for c in comp if c["source"] == source]
        return {"attempted": len(rs), "success_with_events": sum(1 for r in rs if r["has_events"]),
                "tickers_with_events": len({r["ticker"] for r in rs if r["has_events"]}),
                "event_count": sum(int(r["event_count"]) for r in rs),
                "dps_count": sum(int(r["dps_count"]) for r in rs),
                "ex_date_count": sum(int(r["ex_date_count"]) for r in rs),
                "payment_date_count": sum(int(r["payment_date_count"]) for r in rs),
                "declaration_date_count": sum(int(r["declaration_date_count"]) for r in rs),
                "record_date_count": sum(int(r["record_date_count"]) for r in rs),
                "currency_count": sum(int(r["currency_count"]) for r in rs),
                "http_429": sum(1 for r in rs if r["http_status"] == 429),
                "errors": sum(1 for r in rs if r["error"])}
    caps = {s: cap(s) for s in ("SMARTERDIVIDENDS","YAHOO_FINANCE","NASDAQ_DIVIDEND_HISTORY")}
    caps["SMARTERDIVIDENDS"].update({"CURRENT_DIVIDEND_PROFILE": caps["SMARTERDIVIDENDS"]["tickers_with_events"] > 0,
        "RECENT_DIVIDEND_EVENT": caps["SMARTERDIVIDENDS"]["tickers_with_events"] > 0,
        "HISTORICAL_RAISE_CUT_HISTORY": any(bool(r.get("SMARTERDIVIDENDS", {}).get("changes")) for r in results.values()),
        "FULL_HISTORICAL_PAYMENT_EVENTS": False, "EX_DATE_AVAILABLE": True,
        "PAY_DATE_AVAILABLE": True, "DECLARATION_DATE_AVAILABLE": False,
        "RECORD_DATE_AVAILABLE": False, "ADR_DIVIDEND_READY": False,
        "attribution": "https://smarterdividends.com/dividend-api"})
    caps["YAHOO_FINANCE"].update({"CURRENT_DIVIDEND_PROFILE": False,
        "RECENT_DIVIDEND_EVENT": caps["YAHOO_FINANCE"]["tickers_with_events"] > 0,
        "HISTORICAL_RAISE_CUT_HISTORY": False,
        "FULL_HISTORICAL_PAYMENT_EVENTS": False,
        "HISTORICAL_EX_DATE_AMOUNT_SERIES": caps["YAHOO_FINANCE"]["event_count"] > 0,
        "EX_DATE_AVAILABLE": True, "PAY_DATE_AVAILABLE": False,
        "DECLARATION_DATE_AVAILABLE": False, "RECORD_DATE_AVAILABLE": False,
        "ADR_DIVIDEND_READY": False})
    caps["NASDAQ_DIVIDEND_HISTORY"].update({"CURRENT_DIVIDEND_PROFILE": caps["NASDAQ_DIVIDEND_HISTORY"]["tickers_with_events"] > 0,
        "RECENT_DIVIDEND_EVENT": caps["NASDAQ_DIVIDEND_HISTORY"]["tickers_with_events"] > 0,
        "HISTORICAL_RAISE_CUT_HISTORY": False,
        "FULL_HISTORICAL_PAYMENT_EVENTS": caps["NASDAQ_DIVIDEND_HISTORY"]["event_count"] > 0,
        "HISTORICAL_EX_DATE_AMOUNT_SERIES": caps["NASDAQ_DIVIDEND_HISTORY"]["event_count"] > 0,
        "EX_DATE_AVAILABLE": True, "PAY_DATE_AVAILABLE": True,
        "DECLARATION_DATE_AVAILABLE": True, "RECORD_DATE_AVAILABLE": True,
        "ADR_DIVIDEND_READY": False,
        "coverage": "NASDAQ_LISTED_ONLY", "split_adjustment": "NOT_SPLIT_ADJUSTED"})
    summary = {"metadata": {"generated_at": datetime.now(timezone.utc).isoformat(), "sample": len(sample),
        "snapshot": str(SNAPSHOT), "requests": {k: v["attempted"] for k, v in source_meta.items()},
        "note": "One attempt per ticker/source; Yahoo stops on 429; Nasdaq only Nasdaq-listed sample."},
        "source_capability": caps, "source_meta": source_meta,
        "decision": {"SMARTERDIVIDENDS": "B_CURRENT_PROFILE_ONLY",
                     "YAHOO_FINANCE": "B_HISTORICAL_DPS_EX_DATE_ONLY",
                     "NASDAQ_DIVIDEND_HISTORY": "A_ONLY_FOR_NASDAQ_LISTED_NOT_FULL_MARKET",
                     "FULL_MARKET_A": False},
        "results": results}
    OUT_RESULT.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"caps": caps, "decision": summary["decision"], "requests": summary["metadata"]["requests"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
