"""Capture recent free Yahoo OHLC and adjusted prices for PIT event response research."""
from __future__ import annotations
import argparse, csv, json, math, re, time
from datetime import date, datetime, time as clock_time, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo
import requests

NY = ZoneInfo("America/New_York")
UA = "Mozilla/5.0 (compatible; wijouyang-lab/us research collector; contact: 288002660+wijouyang-lab@users.noreply.github.com)"
FIELDS = ["Date","Ticker","Open","High","Low","Close","Adj Open","Adj High","Adj Low","Adj Close","Volume"]
TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-^=]{0,14}$")


def parse_aware(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip(): return None
    try: parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError: return None
    if parsed.tzinfo is None or parsed.utcoffset() is None: return None
    return parsed.astimezone(timezone.utc)


def last_completed_session(as_of_utc: datetime) -> date:
    local = as_of_utc.astimezone(NY)
    cutoff = local.date() if local.time() >= clock_time(16, 0) else local.date() - timedelta(days=1)
    while cutoff.weekday() >= 5: cutoff -= timedelta(days=1)
    return cutoff


def select_universe(events: list[dict[str, Any]], *, as_of_utc: datetime, lookback_days: int = 30, max_symbols: int = 100):
    if lookback_days < 1 or max_symbols < 1: raise ValueError("lookback_days and max_symbols must be positive")
    recent = []
    for event in events:
        seen = parse_aware(event.get("first_seen_at_utc"))
        if not seen or seen > as_of_utc or (as_of_utc-seen).total_seconds() > lookback_days*86400: continue
        if str(event.get("availability_status") or "").lower() != "available": continue
        recent.append((event, seen))
    end = last_completed_session(as_of_utc)
    if not recent: return ["SPY"], end-timedelta(days=7), end, {"recent_event_count":0,"unmapped_event_count":0}
    symbols={"SPY"}; unmapped=0
    for event, _ in recent:
        candidates=list(event.get("tickers") or []) if isinstance(event.get("tickers"),list) else []
        if event.get("queried_ticker"): candidates.append(event["queried_ticker"])
        found=False
        for raw in candidates:
            symbol=str(raw or "").strip().upper().replace("$","").replace(".","-").replace("/","-")
            if TICKER_RE.fullmatch(symbol): symbols.add(symbol); found=True
        if not found and event.get("event_type") not in {"macro_release","central_bank","policy","geopolitical"}: unmapped+=1
    start=min(seen.date() for _,seen in recent)-timedelta(days=7)
    if start>end: start=end-timedelta(days=7)
    ordered=["SPY"]+sorted(symbols-{"SPY"})
    return ordered[:max_symbols],start,end,{"recent_event_count":len(recent),"unmapped_event_count":unmapped}


def positive(value):
    try: number=float(value)
    except (TypeError,ValueError): return None
    return number if math.isfinite(number) and number>0 else None


def fetch_chart_history(ticker: str, start: date, end: date, *, get=requests.get, user_agent: str=UA):
    if end<start: raise ValueError("end date precedes start date")
    symbol=str(ticker).strip().upper().replace(".","-")
    p1=int(datetime.combine(start,clock_time.min,tzinfo=NY).timestamp())
    p2=int(datetime.combine(end+timedelta(days=1),clock_time.min,tzinfo=NY).timestamp())
    url=f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol,safe='.-^=')}"
    response=get(url,params={"period1":p1,"period2":p2,"interval":"1d","events":"div,splits","includePrePost":"false"},
                 headers={"User-Agent":user_agent,"Accept":"application/json"},timeout=20)
    response.raise_for_status(); payload=response.json()
    chart=payload.get("chart") if isinstance(payload,dict) else None
    if not isinstance(chart,dict): raise ValueError("Yahoo chart response is not an object")
    if chart.get("error"): raise ValueError(f"Yahoo chart error: {chart['error']}")
    results=chart.get("result")
    if not isinstance(results,list) or not results: return []
    result=results[0]; stamps=result.get("timestamp") or []
    quotes=(result.get("indicators") or {}).get("quote") or []
    if not quotes: return []
    q=quotes[0]; adj_rows=(result.get("indicators") or {}).get("adjclose") or []
    adjs=adj_rows[0].get("adjclose") if adj_rows else None
    rows=[]
    for i,stamp in enumerate(stamps):
        try: day=datetime.fromtimestamp(int(stamp),timezone.utc).astimezone(NY).date()
        except (TypeError,ValueError,OverflowError,OSError): continue
        if not start<=day<=end: continue
        def raw(key):
            values=q.get(key) or []
            return values[i] if i<len(values) else None
        op,hi,lo,close=(positive(raw(k)) for k in ("open","high","low","close"))
        adj=positive(adjs[i]) if adjs and i<len(adjs) else None
        if close is None: continue
        factor=adj/close if adj is not None else None
        def adjusted(value): return round(value*factor,6) if value is not None and factor is not None else None
        volume=raw("volume")
        try: volume=int(volume) if volume is not None and int(volume)>=0 else None
        except (TypeError,ValueError,OverflowError): volume=None
        rows.append({"Date":day.isoformat(),"Ticker":symbol,"Open":round(op,6) if op is not None else None,
          "High":round(hi,6) if hi is not None else None,"Low":round(lo,6) if lo is not None else None,
          "Close":round(close,6),"Adj Open":adjusted(op),"Adj High":adjusted(hi),"Adj Low":adjusted(lo),
          "Adj Close":round(adj,6) if adj is not None else None,"Volume":volume})
    return rows


def capture_prices(archive_path, output_csv, output_report, *, as_of_utc=None, lookback_days=30, max_symbols=100, get=requests.get, delay_seconds=0.1):
    as_of_utc=as_of_utc or datetime.now(timezone.utc)
    if as_of_utc.tzinfo is None or as_of_utc.utcoffset() is None: raise ValueError("as_of_utc must be timezone-aware")
    as_of_utc=as_of_utc.astimezone(timezone.utc)
    archive=Path(archive_path)
    try: raw_archive=archive.read_bytes(); events=json.loads(raw_archive.decode("utf-8-sig"))
    except (OSError,UnicodeDecodeError,json.JSONDecodeError) as exc: raise ValueError(f"cannot read event archive: {exc}") from exc
    if not isinstance(events,list) or any(not isinstance(x,dict) for x in events): raise ValueError("event archive must be a JSON array of objects")
    csv_path,report_path=Path(output_csv),Path(output_report)
    if csv_path.exists() or report_path.exists(): raise ValueError("refusing to overwrite an existing price CSV or report")
    symbols,start,end,stats=select_universe(events,as_of_utc=as_of_utc,lookback_days=lookback_days,max_symbols=max_symbols)
    rows=[]; reports=[]
    for i,symbol in enumerate(symbols):
        try:
            found=fetch_chart_history(symbol,start,end,get=get)
            rows.extend(found); reports.append({"ticker":symbol,"status":"ok" if found else "empty","row_count":len(found),"error":None})
        except Exception as exc:
            reports.append({"ticker":symbol,"status":"error","row_count":0,"error":f"{type(exc).__name__}: {exc}"})
        if delay_seconds>0 and i<len(symbols)-1: time.sleep(delay_seconds)
    csv_path.parent.mkdir(parents=True,exist_ok=True); tmp=csv_path.with_name(csv_path.name+".tmp")
    with tmp.open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=FIELDS); writer.writeheader(); writer.writerows(rows)
    if csv_path.exists(): tmp.unlink(missing_ok=True); raise ValueError(f"price CSV appeared during write: {csv_path}")
    tmp.replace(csv_path); digest=sha256(csv_path.read_bytes()).hexdigest()
    failed=sum(x["status"]=="error" for x in reports); success=sum(x["status"]=="ok" for x in reports)
    report={"schema_version":"1.0","research_only":True,"trading_signal_generated":False,
      "source":"yahoo_finance_chart_public_endpoint","source_url_template":"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
      "as_of_utc":as_of_utc.isoformat().replace("+00:00","Z"),"study_price_start_date":start.isoformat(),"study_price_end_date":end.isoformat(),
      "lookback_days":lookback_days,"event_archive_path":str(archive),"event_archive_sha256":sha256(raw_archive).hexdigest(),
      "price_csv_path":str(csv_path),"price_csv_sha256":digest,**stats,"requested_symbol_count":len(symbols),
      "successful_symbol_count":success,"failed_symbol_count":failed,"price_row_count":len(rows),
      "status":"complete" if failed==0 and success>0 else ("partial" if rows else "no_price_data"),
      "symbol_reports":reports,"limitations":[
        "Yahoo chart data is free but may be rate-limited or revised.",
        "Adjusted OHLC is derived from adjusted-close factors, not executable fill prices.",
        "Price capture does not verify company-news ticker mapping or annotate event direction/impact.",
        "Historical first-seen times are not reconstructed; only recent archived events choose the price window."]}
    report_path.parent.mkdir(parents=True,exist_ok=True); temp=report_path.with_name(report_path.name+".tmp")
    temp.write_text(json.dumps(report,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")
    if report_path.exists(): temp.unlink(missing_ok=True); raise ValueError(f"price report appeared during write: {report_path}")
    temp.replace(report_path); return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive",required=True); parser.add_argument("--output-csv",required=True); parser.add_argument("--output-report",required=True)
    parser.add_argument("--as-of-utc"); parser.add_argument("--lookback-days",type=int,default=30); parser.add_argument("--max-symbols",type=int,default=100)
    args=parser.parse_args(argv)
    try:
        as_of=parse_aware(args.as_of_utc) if args.as_of_utc else datetime.now(timezone.utc)
        if args.as_of_utc and as_of is None: raise ValueError("--as-of-utc must be timezone-aware ISO-8601")
        report=capture_prices(args.archive,args.output_csv,args.output_report,as_of_utc=as_of,lookback_days=args.lookback_days,max_symbols=args.max_symbols)
    except (OSError,ValueError,OverflowError) as exc: parser.error(str(exc))
    print(json.dumps({k:report[k] for k in ("status","requested_symbol_count","successful_symbol_count","failed_symbol_count","price_row_count","research_only","trading_signal_generated")},indent=2))
    return 0 if report["price_row_count"] else 2


if __name__=="__main__": raise SystemExit(main())
