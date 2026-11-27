#!/usr/bin/env python3
"""Fetch SEC companyfacts/submissions and latest price for Tier A 30."""
import json, time, requests, pandas as pd, yfinance as yf
from pathlib import Path

ROOT=Path(r"C:\Users\ouyan\Documents\deepseek-harness\_diligence")
OUT=Path(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_diligence_data"); OUT.mkdir(exist_ok=True)
u=pd.read_csv(ROOT/"data/research/unified_selection/unified_selection_v1_1.csv")
t=u[u.research_group=="TIER_A"].copy()
fs=pd.read_csv(ROOT/"data/research/fs2/composite_candidates_v1.csv")[["ticker","cik"]].drop_duplicates("ticker")
t=t.merge(fs,on="ticker",how="left")
H={"User-Agent":"independent research contact@example.com"}
rows=[]
for _,r in t.iterrows():
    cik=int(r.cik); c=f"{cik:010d}"
    for kind,url in [("facts",f"https://data.sec.gov/api/xbrl/companyfacts/CIK{c}.json"),("subs",f"https://data.sec.gov/submissions/CIK{c}.json")]:
        p=OUT/f"{r.ticker}_{kind}.json"
        if p.exists(): continue
        for attempt in range(3):
            try:
                x=requests.get(url,headers=H,timeout=40); x.raise_for_status(); p.write_bytes(x.content); break
            except Exception as e:
                time.sleep(2)
        time.sleep(0.15)
    rows.append({"ticker":r.ticker,"company":r.issuer_name,"cik":c,"industry":r.industry})
pd.DataFrame(rows).to_csv(OUT/"companies.csv",index=False)
# prices
tickers=t.ticker.tolist(); yf.set_tz_cache_location(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_yf_tmp")
px=yf.download(tickers,period="5d",interval="1d",group_by="ticker",progress=False,threads=True,auto_adjust=False)
prows=[]
for tk in tickers:
    try:
        x=px[tk].dropna(subset=["Close"]); last=x.iloc[-1]
        prows.append({"ticker":tk,"price_date":x.index[-1].date().isoformat(),"price":float(last["Close"])})
    except Exception: prows.append({"ticker":tk,"price_date":"","price":None})
pd.DataFrame(prows).to_csv(OUT/"prices.csv",index=False)
print(len(rows),len(prows))
