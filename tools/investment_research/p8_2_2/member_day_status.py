"""P8.2.2 mutually exclusive member-day status partition."""
from __future__ import annotations
import csv,json
from collections import defaultdict
from datetime import date,datetime,timezone
from pathlib import Path
import pandas as pd

ROOT=Path(".");O=ROOT/"data/research/p8_2_2"


def main():
    m=pd.read_csv(ROOT/"data/research/historical_universe/sp500_daily.csv");m["date"]=pd.to_datetime(m.date).dt.date
    m=m.drop_duplicates("date").sort_values("date");m=m[(m.date>=date(2000,1,3))&(m.date<=date(2024,12,31))]
    px=pd.read_csv(ROOT/"data/research/pit_data/finsaber_prices_raw.csv",usecols=["date","symbol","open","high","low","close","adjusted_close","volume"])
    px["date"]=pd.to_datetime(px.date).dt.date;px["symbol"]=px.symbol.str.upper();px=px[(px.date>=date(2000,1,3))&(px.date<=date(2024,12,31))]
    dup=set(map(tuple,px[px.duplicated(["date","symbol"],keep=False)][["date","symbol"]].itertuples(index=False,name=None)))
    rec={}
    for r in px.drop_duplicates(["date","symbol"],keep="last").itertuples():
        vals=[r.open,r.high,r.low,r.close,r.adjusted_close,r.volume];finite=all(pd.notna(x) for x in vals)
        positive=finite and all(x>0 for x in (r.open,r.high,r.low,r.close,r.adjusted_close))
        relation=positive and r.low<=min(r.open,r.close) and r.high>=max(r.open,r.close) and r.high>=r.low
        rec[(r.date,r.symbol)]={"close":positive,"full":relation and finite and r.volume>=0,"relation":relation,"volume":r.volume if finite else None}
    cls={}
    with (ROOT/"data/research/p8_2_1/ticker_anomaly_audit.csv").open(encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):cls[(date.fromisoformat(r["anomaly_date"]),r["ticker"])]=r["classification"]
    counts=defaultdict(int);years=defaultdict(lambda:defaultdict(int));tick=defaultdict(lambda:defaultdict(int))
    for row in m.itertuples():
        d=row.date
        for t in {x.strip().upper() for x in str(row.tickers).split(",") if x.strip()}:
            total=counts["member_days"];counts["member_days"]+=1;years[d.year]["member_days"]+=1;tick[t]["member_days"]+=1
            x=rec.get((d,t));c=cls.get((d,t))
            if (d,t) in dup:status="DUPLICATE_OR_CONFLICT"
            elif not x or not x["close"]:status="UNKNOWN_MISSING_DATA"
            elif not x["relation"]:status="INVALID_OHLC_RELATION"
            elif x["volume"] is None or x["volume"]<0:status="INVALID_VOLUME"
            elif c=="VERIFIED_CORRUPT":status="VERIFIED_CORRUPT"
            elif c=="UNRESOLVED":status="UNRESOLVED"
            elif x["volume"]==0 or c=="ZERO_VOLUME_OR_STALE":status="ZERO_VOLUME_OR_STALE"
            elif x["full"]:status="VALID_VERIFIED_TRADABLE"
            else:status="OTHER_INVALID"
            counts[status]+=1;years[d.year][status]+=1;tick[t][status]+=1
    statuses=["VALID_VERIFIED_TRADABLE","UNKNOWN_MISSING_DATA","VERIFIED_CORRUPT","ZERO_VOLUME_OR_STALE","UNRESOLVED","INVALID_OHLC_RELATION","INVALID_VOLUME","DUPLICATE_OR_CONFLICT","OTHER_INVALID"]
    assert sum(counts[s] for s in statuses)==counts["member_days"]
    summary={"generated_at":datetime.now(timezone.utc).isoformat(),"denominator":counts["member_days"],"statuses":{s:counts[s] for s in statuses},"sum":sum(counts[s] for s in statuses),"duplicate_rows":len(dup),"policy":"exactly one final status per member-day; priority duplicate > unknown > OHLC > volume > corrupt > unresolved > zero/stale > valid"}
    (O/"member_day_status_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    with (O/"member_day_status_by_year.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["year"]+statuses);w.writeheader()
        for y in sorted(years):w.writerow({"year":y,**{s:years[y][s] for s in statuses}})
    with (O/"member_day_status_by_ticker.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["ticker"]+statuses);w.writeheader()
        for t in sorted(tick):w.writerow({"ticker":t,**{s:tick[t][s] for s in statuses}})
    print(json.dumps(summary,indent=2))


if __name__=="__main__":raise SystemExit(main())
