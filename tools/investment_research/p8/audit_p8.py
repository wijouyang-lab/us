"""P8.1 audit: reproduce monthly PIT returns and identify extreme contributors."""
from __future__ import annotations
import json, math
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(".")
P8 = ROOT / "data/research/p8"
AS_OF = date(2024, 12, 31)
TOP_N = 20
COST_BPS = 10.0


def members_frame():
    m = pd.read_csv(ROOT/"data/research/historical_universe/sp500_daily.csv")
    m["date"] = pd.to_datetime(m["date"]).dt.date
    return m.drop_duplicates("date").sort_values("date")


def main():
    px = pd.read_csv(ROOT/"data/research/pit_data/finsaber_prices_raw.csv", usecols=["date","symbol","open","close","adjusted_close"])
    px["date"] = pd.to_datetime(px.date); px["symbol"] = px.symbol.str.upper()
    px = px[(px.date >= "2000-01-03") & (px.date <= "2024-12-31")].copy()
    px["adj_open"] = px.open * (px.adjusted_close / px.close)
    close = px.pivot_table(index="date", columns="symbol", values="adjusted_close", aggfunc="last").sort_index()
    open_ = px.pivot_table(index="date", columns="symbol", values="adj_open", aggfunc="last").reindex(close.index)
    mom120 = close / close.shift(120) - 1
    vol60 = close.pct_change().rolling(60).std() * math.sqrt(252)
    factors = {"MOMENTUM_120": mom120, "LOW_VOL_60": -vol60}
    dates = list(close.index.date); pos = {d:i for i,d in enumerate(dates)}
    s = pd.Series(dates, index=pd.to_datetime(dates))
    month_ends = list(s.groupby([s.index.year,s.index.month]).last().values)
    m = members_frame(); md=list(m.date); mt=list(m.tickers)
    monthly = []; contrib = defaultdict(float); extreme = []; gaps=[]; all_rows=[]
    prev = {k:set() for k in factors}
    for mi, mdte in enumerate(month_ends[:-1]):
        p = np.searchsorted(md, mdte, side="right")-1
        if p<0: continue
        members={x.strip().upper() for x in str(mt[p]).split(",") if x.strip()}
        di=pos.get(mdte)
        if di is None or di+1>=len(dates): continue
        entry=dates[di+1]; ndi=pos.get(month_ends[mi+1])
        if ndi is None or ndi+1>=len(dates): continue
        exitd=dates[ndi+1]
        cols=[c for c in close.columns if c in members]
        avail=[c for c in cols if pd.notna(close.loc[pd.Timestamp(mdte),c]) and pd.notna(open_.loc[pd.Timestamp(entry),c]) and pd.notna(open_.loc[pd.Timestamp(exitd),c])]
        if len(avail)<30: continue
        gaps.append((exitd-entry).days)
        for name,f in factors.items():
            vals=[(c,f.loc[pd.Timestamp(mdte),c]) for c in avail if pd.notna(f.loc[pd.Timestamp(mdte),c]) and np.isfinite(f.loc[pd.Timestamp(mdte),c])]
            vals.sort(key=lambda z:-z[1]); hold={c for c,_ in vals[:TOP_N]}
            if not hold: continue
            for c in hold:
                r=open_.loc[pd.Timestamp(exitd),c]/open_.loc[pd.Timestamp(entry),c]-1
                contrib[(name,c)] += r/len(hold)
                all_rows.append({"strategy":name,"formation":str(mdte),"entry":str(entry),"exit":str(exitd),"ticker":c,"return":r,"entry_price":float(open_.loc[pd.Timestamp(entry),c]),"exit_price":float(open_.loc[pd.Timestamp(exitd),c])})
            gross=float(np.mean([open_.loc[pd.Timestamp(exitd),c]/open_.loc[pd.Timestamp(entry),c]-1 for c in hold]))
            turn=len(hold ^ prev[name])/len(hold)
            net=gross-COST_BPS/10000*turn*2
            monthly.append({"strategy":name,"formation":str(mdte),"entry":str(entry),"exit":str(exitd),"gross":gross,"net":net,"turnover":turn,"n":len(hold)})
            prev[name]=hold
            if gross>0.5: extreme.append((name,str(mdte),gross))
    df=pd.DataFrame(monthly); df.to_csv(P8/"pit_monthly_audit.csv",index=False)
    pd.DataFrame(all_rows).to_csv(P8/"pit_trades_audit.csv",index=False)
    summary={}
    for name in factors:
        x=df[df.strategy==name]; r=x.net.values; eq=np.cumprod(1+r)
        yrs=len(r)/12
        top=x.sort_values("gross",ascending=False).head(10)
        summary[name]={"months":len(r),"cagr":float(eq[-1]**(1/yrs)-1) if yrs else None,
                       "max_month":float(x.gross.max()),"min_month":float(x.gross.min()),
                       "gross_gt_50pct_months":int((x.gross>0.5).sum()),
                       "avg_gap_days":float(np.mean(gaps)) if gaps else None,
                       "top_months":top[["formation","gross","n"]].to_dict("records"),
                       "top_contributors":[{"ticker":c,"sum_contrib":v} for (n,c),v in sorted(contrib.items(),key=lambda z:-z[1]) if n==name][:10]}
    audit={"generated_at":datetime.now(timezone.utc).isoformat(),"status":"AUDIT_COMPLETE",
           "price_symbols":int(close.shape[1]),"price_dates":len(close),
           "member_rows":len(m),"summary":summary,
           "extreme_months":extreme[:20],
           "note":"Same reproduction logic as P8; audit only, no parameter change."}
    (P8/"p8_audit.json").write_text(json.dumps(audit,indent=2),encoding="utf-8")
    print(json.dumps(audit,indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
