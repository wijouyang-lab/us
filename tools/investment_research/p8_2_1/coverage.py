"""P8.2.1 complete OHLCV coverage with full member-day denominator."""
from __future__ import annotations
import csv,json
from collections import defaultdict
from datetime import date,datetime,timezone
from pathlib import Path
import pandas as pd

ROOT=Path("."); OUT=ROOT/"data/research/p8_2_1"


def main():
    m=pd.read_csv(ROOT/"data/research/historical_universe/sp500_daily.csv");m["date"]=pd.to_datetime(m.date).dt.date
    m=m.drop_duplicates("date").sort_values("date");m=m[(m.date>=date(2000,1,3))&(m.date<=date(2024,12,31))]
    px=pd.read_csv(ROOT/"data/research/pit_data/finsaber_prices_raw.csv",usecols=["date","symbol","open","high","low","close","adjusted_close","volume"])
    px["date"]=pd.to_datetime(px.date).dt.date;px["symbol"]=px.symbol.str.upper();px=px[(px.date>=date(2000,1,3))&(px.date<=date(2024,12,31))]
    dup=int(px.duplicated(["date","symbol"]).sum())
    px=px.drop_duplicates(["date","symbol"],keep="last")
    rec={}
    for r in px.itertuples():
        vals=[r.open,r.high,r.low,r.close,r.adjusted_close,r.volume]
        finite=all(pd.notna(x) for x in vals)
        positive=finite and r.open>0 and r.high>0 and r.low>0 and r.close>0 and r.adjusted_close>0
        relation=positive and r.low<=min(r.open,r.close) and r.high>=max(r.open,r.close) and r.high>=r.low
        vol_ok=finite and r.volume>=0
        rec[(r.date,r.symbol)]={"close":positive,"full":relation and vol_ok,"volume":r.volume if finite else None}
    cls={}
    with (OUT/"ticker_anomaly_audit.csv").open(encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f): cls[(date.fromisoformat(r["anomaly_date"]),r["ticker"])]=r["classification"]
    totals=defaultdict(int); years=defaultdict(lambda:defaultdict(int)); tick=defaultdict(lambda:defaultdict(int))
    for row in m.itertuples():
        d=row.date
        for t in {x.strip().upper() for x in str(row.tickers).split(",") if x.strip()}:
            x=rec.get((d,t)); c=cls.get((d,t))
            totals["member_days"]+=1;years[d.year]["member_days"]+=1;tick[t]["member_days"]+=1
            if not x or not x["close"]:
                totals["unknown"]+=1;years[d.year]["unknown"]+=1;tick[t]["unknown"]+=1;continue
            totals["valid_close"]+=1;years[d.year]["valid_close"]+=1;tick[t]["valid_close"]+=1
            if x["full"]:
                totals["full_ohlcv"]+=1;years[d.year]["full_ohlcv"]+=1;tick[t]["full_ohlcv"]+=1
            if c=="VERIFIED_CORRUPT":
                totals["corrupt"]+=1;years[d.year]["corrupt"]+=1;tick[t]["corrupt"]+=1
            elif c=="UNRESOLVED":
                totals["unresolved"]+=1;years[d.year]["unresolved"]+=1;tick[t]["unresolved"]+=1
            elif c=="ZERO_VOLUME_OR_STALE":
                totals["zero_or_stale"]+=1;years[d.year]["zero_or_stale"]+=1;tick[t]["zero_or_stale"]+=1
            if x["full"] and (x["volume"] or 0)>0 and c not in ("VERIFIED_CORRUPT","UNRESOLVED","ZERO_VOLUME_OR_STALE"):
                totals["verified_tradable"]+=1;years[d.year]["verified_tradable"]+=1;tick[t]["verified_tradable"]+=1
    def p(a,b):return round(a/b,8) if b else None
    summary={"generated_at":datetime.now(timezone.utc).isoformat(),"denominator":"all effective-dated S&P 500 member-days",
             "duplicate_ticker_date_rows":dup,"totals":{**totals,"original_close_coverage":p(totals["valid_close"],totals["member_days"]),
             "full_ohlcv_coverage":p(totals["full_ohlcv"],totals["member_days"]),
             "verified_tradable_coverage":p(totals["verified_tradable"],totals["member_days"])},
             "policy":"full OHLCV = positive OHLC, low<=open/close<=high, finite volume; tradable also volume>0 and no unresolved/corrupt/stale flag"}
    (OUT/"ohlcv_coverage_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    with (OUT/"ohlcv_coverage_by_year.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["year","member_days","valid_close","full_ohlcv","verified_tradable","corrupt","unresolved","zero_or_stale","unknown","original_close_coverage","full_ohlcv_coverage","verified_tradable_coverage"]);w.writeheader()
        for y in sorted(years):
            x=years[y];w.writerow({"year":y,**x,"original_close_coverage":p(x["valid_close"],x["member_days"]),"full_ohlcv_coverage":p(x["full_ohlcv"],x["member_days"]),"verified_tradable_coverage":p(x["verified_tradable"],x["member_days"])})
    with (OUT/"ohlcv_coverage_by_ticker.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["ticker","member_days","valid_close","full_ohlcv","verified_tradable","corrupt","unresolved","zero_or_stale","unknown","original_close_coverage","full_ohlcv_coverage","verified_tradable_coverage"]);w.writeheader()
        for t in sorted(tick):
            x=tick[t];w.writerow({"ticker":t,**x,"original_close_coverage":p(x["valid_close"],x["member_days"]),"full_ohlcv_coverage":p(x["full_ohlcv"],x["member_days"]),"verified_tradable_coverage":p(x["verified_tradable"],x["member_days"])})
    print(json.dumps(summary,indent=2))


if __name__=="__main__":raise SystemExit(main())
