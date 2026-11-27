#!/usr/bin/env python3
"""Build 8-quarter income/cash-flow table for SFM/LRN/ADUS from SEC XBRL."""
import json
from pathlib import Path
import pandas as pd, numpy as np

DATA=Path(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_diligence_data")
OUT=Path(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_decision_out"); OUT.mkdir(exist_ok=True)
TAGS={"revenue":["Revenues","RevenueFromContractWithCustomerExcludingAssessedTax"],"net_income":["NetIncomeLoss"],"ocf":["NetCashProvidedByUsedInOperatingActivities"],"capex":["PaymentsToAcquirePropertyPlantAndEquipment","PaymentsToAcquireProductiveAssets"]}

def ent(f,t):
 d=pd.DataFrame(f[t]["units"]["USD"]); d["start"]=pd.to_datetime(d.start); d["end"]=pd.to_datetime(d.end); d["days"]=(d.end-d.start).dt.days; return d
rows=[]
for tk in ["SFM","LRN","ADUS"]:
 f=json.load(open(DATA/f"{tk}_facts.json"))["facts"]["us-gaap"]
 # choose tags with most recent quarterly facts
 for name,tags in TAGS.items():
  pass
 ser={}
 for name,tags in TAGS.items():
  best=None
  for t in tags:
   if t not in f: continue
   d=ent(f,t); d=d[d.form.astype(str).str.contains("10-Q|10-K") & d.end.notna()]
   if len(d): best=d
  ser[name]=best
 # quarter ends from revenue 3-month 10-Q and annual ends
 rev=ser["revenue"]; q=rev[(rev.form.astype(str).str.contains("10-Q"))&(rev.days.between(80,100))].drop_duplicates("end").sort_values("end")
 ends=list(q.end)[-8:]
 if len(ends)<8: ends=list(rev.end.drop_duplicates().sort_values())[-8:]
 for e in ends:
  rec={"ticker":tk,"period_end":e.date().isoformat()}
  for name in ["revenue","net_income"]:
   d=ser[name]; x=d[(d.end==e)&(d.days.between(80,100))]
   if len(x): rec[name]=float(x.val.iloc[-1]); rec[name+"_period"]="3M"
   else:
    # Q4 = FY annual - 9M YTD
    fy=d[(d.end==e)&(d.days.between(330,400))]
    prev=d[(d.end<e)&(d.end>=e-pd.Timedelta(days=100))&(d.days.between(250,290))]
    if len(fy) and len(prev): rec[name]=float(fy.val.iloc[-1])-float(prev.val.iloc[-1]); rec[name+"_period"]="Q4_DERIVED"
    else: rec[name]=np.nan; rec[name+"_period"]="UNAVAILABLE"
  for name in ["ocf","capex"]:
   d=ser[name]; y=d[(d.end==e)&(d.days.between(80,280))]
   if len(y):
    val=float(y.val.iloc[-1]); days=int(y.days.iloc[-1]); rec[name+"_period"]=f"YTD_{days}D"
    if days<=100: rec[name]=val
    else:
     # prior YTD within same fiscal year
     p=d[(d.end<e)&(d.start>=y.start.iloc[-1]-pd.Timedelta(days=5))].sort_values("end")
     rec[name]=val-float(p.iloc[-1].val) if len(p) else np.nan
   else:
    fy=d[(d.end==e)&(d.days.between(330,400))]; prev=d[(d.end<e)&(d.end>=e-pd.Timedelta(days=100))&(d.days.between(250,290))]
    rec[name]=float(fy.val.iloc[-1])-float(prev.val.iloc[-1]) if len(fy) and len(prev) else np.nan
    rec[name+"_period"]="Q4_DERIVED" if pd.notna(rec[name]) else "UNAVAILABLE"
  rows.append(rec)
df=pd.DataFrame(rows); df["fcf"]=df.ocf-df.capex; df.to_csv(OUT/"quarterly_financials.csv",index=False)
print(df.to_string(index=False))
