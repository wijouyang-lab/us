#!/usr/bin/env python3
"""PR633 audit: TTM, debt components, period consistency, valuation before/after."""
import json, math
from pathlib import Path
import pandas as pd, numpy as np

ROOT=Path(r"C:\Users\ouyan\Documents\deepseek-harness\_audit")
DATA=Path(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_diligence_data")
OLD=Path(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_diligence_report")
OUT=Path(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_audit_out"); OUT.mkdir(exist_ok=True)
co=pd.read_csv(DATA/"companies.csv",dtype={"cik":str}); px=pd.read_csv(DATA/"prices.csv")
old=pd.read_csv(OLD/"valuation_comparison.csv")

REV=["RevenueFromContractWithCustomerExcludingAssessedTax","Revenues","SalesRevenueNet","RevenueFromContractWithCustomerIncludingAssessedTax"]
OI=["OperatingIncomeLoss"]; NI=["NetIncomeLoss","ProfitLoss"]; OCF=["NetCashProvidedByUsedInOperatingActivities"]
CAPEX=["PaymentsToAcquirePropertyPlantAndEquipment","PaymentsToAcquireProductiveAssets","PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssets"]
DA=["DepreciationDepletionAndAmortization","DepreciationAmortizationAndAccretionNet","DepreciationAndAmortization"]
CASH=["CashAndCashEquivalentsAtCarryingValue","CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"]
TOTAL_DEBT=["LongTermDebt","DebtLongtermAndShorttermCombinedAmount","DebtInstrumentCarryingAmount","NotesPayable","SeniorNotes"]
DEBT_PARTS=["LongTermDebtNoncurrent","LongTermDebtCurrent","DebtCurrent","ConvertibleDebtNoncurrent","FinanceLeaseLiabilityNoncurrent","FinanceLeaseLiabilityCurrent","NotesPayable","ConvertibleNotesPayable","LineOfCredit"]

def ent(facts,tag):
    try: u=facts[tag]["units"]
    except Exception: return pd.DataFrame()
    rows=[]
    for unit,arr in u.items():
        for x in arr: rows.append({**x,"unit":unit})
    return pd.DataFrame(rows)

def dur(df):
    df=df.copy(); df["start"]=pd.to_datetime(df.start,errors="coerce"); df["end"]=pd.to_datetime(df.end,errors="coerce"); df["days"]=(df.end-df.start).dt.days; return df

def annual(facts,tags):
    best=pd.DataFrame(); bt=None; be=None
    for t in tags:
        d=ent(facts,t)
        if len(d)==0: continue
        d=d[d.form.astype(str).str.contains("10-K|20-F|40-F")]; d=dur(d)
        d=d[(d.days>=330)&(d.days<=400)].dropna(subset=["end","val"]).sort_values("end").drop_duplicates("end",keep="last")
        if len(d)==0: continue
        if be is None or d.end.max()>be: best,bt,be=d,t,d.end.max()
    return (best.tail(1) if len(best) else best),bt

def interim(facts,tags):
    """Latest YTD interim (80-280 days) from 10-Q; prefer longest duration at latest end."""
    best=pd.DataFrame(); bt=None; be=None
    for t in tags:
        d=ent(facts,t)
        if len(d)==0: continue
        d=d[d.form.astype(str).str.contains("10-Q")]; d=dur(d)
        d=d[(d.days>=80)&(d.days<=280)].dropna(subset=["end","val"])
        if len(d)==0: continue
        e=d.end.max(); x=d[d.end==e].sort_values("days").tail(1)
        if be is None or e>be: best,bt,be=x,t,e
    return best,bt

def prior_ytd(facts,tags,latest):
    if len(latest)==0: return pd.DataFrame(),None
    e=latest.iloc[-1].end; st=latest.iloc[-1].start; days=latest.iloc[-1].days
    best=pd.DataFrame(); bt=None
    for t in tags:
        d=ent(facts,t)
        if len(d)==0: continue
        d=dur(d); d=d[d.form.astype(str).str.contains("10-Q")]
        d=d[d.end.notna()]
        target=e-pd.DateOffset(years=1)
        d=d[(d.end>=target-pd.Timedelta(days=10))&(d.end<=target+pd.Timedelta(days=10))]
        d=d[(d.days>=days-15)&(d.days<=days+15)]
        if len(d): best=d.sort_values("end").tail(1); bt=t
    return best,bt

def compute_ttm(fy,ytd,prior):
    if fy is None or ytd is None or prior is None: return None
    return fy + ytd - prior

def ttm(facts,tags):
    fy,ft=annual(facts,tags); it,itag=interim(facts,tags)
    if len(fy)==0: return None,"NO_ANNUAL",None,None,None,None,None
    fyv=float(fy.iloc[-1].val)
    if len(it)==0 or it.iloc[-1].end<=fy.iloc[-1].end:
        return None,"TTM_UNAVAILABLE_FY_ONLY",fy.iloc[-1].end.date().isoformat(),None,None,fyv,None
    pv,pt=prior_ytd(facts,tags,it)
    if len(pv)==0: return None,"TTM_UNAVAILABLE_YTD_PRIOR_MISSING",fy.iloc[-1].end.date().isoformat(),it.iloc[-1].end.date().isoformat(),None,fyv,float(it.iloc[-1].val)
    t=compute_ttm(fyv,float(it.iloc[-1].val),float(pv.iloc[-1].val))
    return t,"FY+YTD-PRIOR_YTD",fy.iloc[-1].end.date().isoformat(),it.iloc[-1].end.date().isoformat(),float(pv.iloc[-1].val),fyv,float(it.iloc[-1].val)

def inst(facts,tags):
    d=pd.DataFrame(); bt=None; be=None
    for t in tags:
        x=ent(facts,t)
        if len(x)==0: continue
        x=x[x.end.notna()].copy(); x["end"]=pd.to_datetime(x.end)
        if be is None or x.end.max()>be: d,bt,be=x,t,x.end.max()
    if len(d)==0: return None,None,None
    d=d.sort_values("end").drop_duplicates("end",keep="last"); x=d.iloc[-1]
    return float(x.val),x.end.date().isoformat(),bt

def debt(facts):
    total=None; tt=None; date=None
    for t in TOTAL_DEBT:
        val,dt,at=inst(facts,[t])
        if val is not None: total,tt,date=val,t,dt; break
    parts={}; total_parts=0.0; pdates=[]
    for t in DEBT_PARTS:
        val,dt,at=inst(facts,[t])
        if val is not None:
            parts[t]=val; total_parts+=val; pdates.append(dt)
    if total is not None:
        return total,"TOTAL_TAG",date,parts,tt,False
    if parts:
        return total_parts,"SUM_COMPONENTS",max(pdates),parts,"SUM_COMPONENTS",False
    return None,"N/A",None,{},"N/A",True

rows=[]; debts=[]; periods=[]
for _,c in co.iterrows():
    tk=c.ticker; facts=json.load(open(DATA/f"{tk}_facts.json"))["facts"].get("us-gaap",{})
    vals={}; states={}; details={}; dvals={}
    for name,tags in [("revenue",REV),("operating_income",OI),("net_income",NI),("ocf",OCF),("capex",CAPEX)]:
        v,why,fy,it,prior,fyv,ytdv=ttm(facts,tags); vals[name]=v; states[name]=why; details[name]=(fy,it,prior); dvals[name]=(fyv,ytdv,prior)
    da,_,_=inst(facts,DA); cash,cd,ct=inst(facts,CASH)
    dbt,dmethod,ddate,parts,dflag,_=debt(facts)
    # shares: dei latest, sum distinct classes at latest end; fallback diluted weighted
    sh=None; shdate=None; shsrc="N/A"
    try:
        de=json.load(open(DATA/f"{tk}_facts.json"))["facts"]["dei"]["EntityCommonStockSharesOutstanding"]["units"]["shares"]
        de=pd.DataFrame(de); de["end"]=pd.to_datetime(de.end); latest=de.end.max(); z=de[de.end==latest]
        # unique vals by class/value; sum distinct values
        sh=float(z.val.drop_duplicates().sum()); shdate=latest.date().isoformat(); shsrc="dei EntityCommonStockSharesOutstanding"
    except Exception:
        try:
            de=json.load(open(DATA/f"{tk}_facts.json"))["facts"]["us-gaap"]["WeightedAverageNumberOfDilutedSharesOutstanding"]["units"]["shares"]
            de=pd.DataFrame(de); de["end"]=pd.to_datetime(de.end); latest=de.end.max(); sh=float(de[de.end==latest].val.iloc[-1]); shdate=latest.date().isoformat(); shsrc="weighted diluted fallback"
        except Exception: pass
    price=float(px[px.ticker==tk].iloc[0].price); pdate=px[px.ticker==tk].iloc[0].price_date
    mcap=price*sh if sh else None
    if tk=="NRDS": mcap=754932685.0; sh=None; shsrc="FS2 market_cap fallback 2026-11-05"
    ev=(mcap+dbt-cash) if mcap is not None and dbt is not None and cash is not None else None
    ebitda=(vals["operating_income"]+da) if vals["operating_income"] is not None and da is not None else None
    fcf=(vals["ocf"]-vals["capex"]) if vals["ocf"] is not None and vals["capex"] is not None else None
    pe=(mcap/vals["net_income"]) if mcap and vals["net_income"] and vals["net_income"]>0 else None
    ps=(mcap/vals["revenue"]) if mcap and vals["revenue"] and vals["revenue"]>0 else None
    ev_fcf=(ev/fcf) if ev and fcf and fcf>0 else None; ev_ebitda=(ev/ebitda) if ev and ebitda and ebitda>0 else None
    nd=(dbt-cash) if dbt is not None and cash is not None else None
    row={"ticker":tk,"company":c.company,"price":price,"price_date":pdate,"shares":sh,"share_date":shdate,"share_source":shsrc,
         "market_cap":mcap,"cash":cash,"cash_date":cd,"total_debt":dbt,"debt_date":ddate,"debt_method":dmethod,
         "net_debt":nd,"revenue_ttm":vals["revenue"],"operating_income_ttm":vals["operating_income"],"net_income_ttm":vals["net_income"],
         "ocf_ttm":vals["ocf"],"capex_ttm":vals["capex"],"fcf_ttm":fcf,"eps_ttm":(vals["net_income"]/sh) if vals["net_income"] is not None and sh else None,"da":da,"ebitda":ebitda,
         "pe_ttm":pe,"ps_ttm":ps,"ev_ebitda_ttm":ev_ebitda,"ev_fcf_ttm":ev_fcf,"fcf_yield_ttm":(fcf/mcap) if fcf and mcap else None,
         "net_debt_ebitda":(nd/ebitda) if nd is not None and ebitda and ebitda>0 else None,
         "ttm_method":states["revenue"],"ttm_fy":details["revenue"][0],"ttm_ytd":details["revenue"][1],"ttm_prior_ytd":details["revenue"][2],
         "revenue_fy":dvals["revenue"][0],"revenue_ytd":dvals["revenue"][1],"revenue_prior_ytd":dvals["revenue"][2],
         "net_income_fy":dvals["net_income"][0],"net_income_ytd":dvals["net_income"][1],"net_income_prior_ytd":dvals["net_income"][2],
         "ocf_fy":dvals["ocf"][0],"ocf_ytd":dvals["ocf"][1],"ocf_prior_ytd":dvals["ocf"][2],
         "capex_fy":dvals["capex"][0],"capex_ytd":dvals["capex"][1],"capex_prior_ytd":dvals["capex"][2],
         "source":"SEC XBRL companyfacts; price yfinance 2026-11-25"}
    rows.append(row)
    debts.append({"ticker":tk,"total_debt":dbt,"method":dmethod,"date":ddate,"components":json.dumps(parts),"cash":cash,"net_debt":nd})
    for name in ["revenue","net_income","ocf","capex"]:
        fy,it,prior=details[name]; periods.append({"ticker":tk,"metric":name,"fy_end":fy,"ytd_end":it,"prior_ytd":prior,"ytd_days":(pd.Timestamp(it)-pd.Timestamp(fy)).days if fy and it else None,"method":states[name]})
pd.DataFrame(rows).to_csv(OUT/"ttm_metrics.csv",index=False)
pd.DataFrame(debts).to_csv(OUT/"balance_sheet_debt_audit.csv",index=False)
pd.DataFrame(periods).to_csv(OUT/"quarter_period_audit.csv",index=False)
# before after
b=old.set_index("ticker"); a=pd.DataFrame(rows).set_index("ticker")
ba=[]
for t in a.index:
    ba.append({"ticker":t,"company":a.loc[t,"company"],"pe_before":b.loc[t,"pe"] if t in b.index else None,"pe_after":a.loc[t,"pe_ttm"],
               "ev_fcf_before":b.loc[t,"ev_fcf"] if t in b.index else None,"ev_fcf_after":a.loc[t,"ev_fcf_ttm"],
               "fcf_yield_before":b.loc[t,"fcf_yield"] if t in b.index else None,"fcf_yield_after":a.loc[t,"fcf_yield_ttm"],
               "debt_before":b.loc[t,"debt"] if t in b.index else None,"debt_after":a.loc[t,"total_debt"],
               "ttm_method":a.loc[t,"ttm_method"]})
pd.DataFrame(ba).to_csv(OUT/"valuation_before_after.csv",index=False)
print(len(rows),pd.DataFrame(rows).ttm_method.value_counts().to_dict())
print(pd.DataFrame(rows)[["ticker","revenue_ttm","net_income_ttm","fcf_ttm","pe_ttm","ev_fcf_ttm","net_debt_ebitda"]].to_string(index=False))
