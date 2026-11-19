"""P8.4 pre-research audit: eligibility thresholds, label missingness, denominators."""
from __future__ import annotations
import json, math
from datetime import date, datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd

O=Path("data/research/p8_4_market_neutral_alpha"); P83=Path("data/research/p8_3_valid_data_alpha")


def main():
    panel=pd.read_parquet(P83/"valid_research_panel.parquet");panel["date"]=pd.to_datetime(panel.date);panel["year"]=panel.date.dt.year
    # label missingness by year/horizon
    rows=[]
    for (y,h),g in panel.groupby(["year","horizon"]):
        rows.append({"year":int(y),"horizon":int(h),"rows":len(g),"valid":int(g.valid.sum()),"labeled":int(g.label.notna().sum()),
                     "label_missing":int((g.valid & g.label.isna()).sum()),
                     "label_coverage":float(g.label.notna().sum()/max(g.valid.sum(),1))})
    pd.DataFrame(rows).to_csv(O/"label_missingness_audit.csv",index=False)
    # price volatility quintile missingness
    px=pd.read_csv("data/research/pit_data/finsaber_prices_raw.csv",usecols=["date","symbol","adjusted_close"])
    px["date"]=pd.to_datetime(px.date);px["symbol"]=px.symbol.str.upper();px=px[(px.date>="2000-01-03")&(px.date<="2024-12-31")]
    c=px.pivot_table(index="date",columns="symbol",values="adjusted_close",aggfunc="last").sort_index()
    v=c.pct_change(fill_method=None).rolling(60).std()*math.sqrt(252)
    p2=panel.copy();p2["vol60"]=[v.iloc[v.index.get_indexer([d])[0]].get(t,np.nan) if d in v.index and t in v.columns else np.nan for d,t in zip(p2.date,p2.ticker)]
    p2=p2[p2.valid & p2.vol60.notna()].copy();p2["volq"]=pd.qcut(p2.vol60,5,labels=False,duplicates="drop")
    vr=p2.groupby("volq").agg(rows=("label","size"),labeled=("label","count")).reset_index();vr["missing_rate"]=1-vr.labeled/vr.rows
    vr.to_csv(O/"label_missing_by_volatility.csv",index=False)
    # threshold audit on raw adjusted close returns
    r=c.pct_change(fill_method=None)
    threshold=[]
    for k in (3.0,5.0,10.0):
        m=(r.abs()>k); dates_by=m.stack(); dates_by=dates_by[dates_by]
        threshold.append({"threshold_x":k,"ticker_days":int(dates_by.sum()),"unique_tickers":int(m.any().sum()),
                          "gme_days":int(m["GME"].sum()) if "GME" in m else 0,
                          "policy":"diagnostic sensitivity only; primary remains 5x"})
    pd.DataFrame(threshold).to_csv(O/"eligibility_filter_audit.csv",index=False)
    member=1095490
    denom={"generated_at":datetime.now(timezone.utc).isoformat(),"all_member_days":member,
           "p83_panel_rows":len(panel),"p83_unique_date_ticker":int(panel[["date","ticker"]].drop_duplicates().shape[0]),
           "p83_unique_dates":int(panel.date.nunique()),"p83_valid_rows":int(panel.valid.sum()),
           "p83_labeled_rows":int(panel.label.notna().sum()),
           "warning":"352,036 panel rows are three horizon samples, not the 1,095,490 member-day denominator; do not mix."}
    (O/"coverage_denominator_audit.json").write_text(json.dumps(denom,indent=2),encoding="utf-8")
    summary={"generated_at":denom["generated_at"],"label_rows":len(rows),"thresholds":threshold,"panel_rows":len(panel),
             "label_missing_rows":int((panel.valid & panel.label.isna()).sum()),
             "note":"Missing labels are NaN/CENSORED; 5x remains primary; 3x/10x are sensitivity."}
    (O/"audit_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))


if __name__=="__main__":raise SystemExit(main())
