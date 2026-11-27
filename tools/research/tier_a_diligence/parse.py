#!/usr/bin/env python3
"""Parse SEC facts into annual/quarter metrics and valuation for Tier A 30."""
import json, math
from pathlib import Path
import pandas as pd

ROOT=Path(r"C:\Users\ouyan\Documents\deepseek-harness\_diligence")
DATA=Path(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_diligence_data")
OUT=Path(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_diligence_out"); OUT.mkdir(parents=True, exist_ok=True)
co=pd.read_csv(DATA/"companies.csv",dtype={"cik":str})
px=pd.read_csv(DATA/"prices.csv")

REV=["RevenueFromContractWithCustomerExcludingAssessedTax","Revenues","SalesRevenueNet","RevenueFromContractWithCustomerIncludingAssessedTax","OtherSalesRevenueNet","RevenueOtherManufacturedProducts"]
GP=["GrossProfit"]
OI=["OperatingIncomeLoss"]
NI=["NetIncomeLoss","ProfitLoss"]
EPS=["EarningsPerShareDiluted","EarningsPerShareBasic"]
OCF=["NetCashProvidedByUsedInOperatingActivities"]
CAPEX=["PaymentsToAcquirePropertyPlantAndEquipment","PaymentsToAcquireProductiveAssets","PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssets"]
DA=["DepreciationDepletionAndAmortization","DepreciationAmortizationAndAccretionNet","DepreciationAndAmortization"]
SBC=["ShareBasedCompensation","AllocatedShareBasedCompensationExpense"]
CASH=["CashAndCashEquivalentsAtCarryingValue","CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"]
DEBT=["LongTermDebtNoncurrent","LongTermDebtCurrent","DebtCurrent","ConvertibleDebtNoncurrent","LongTermDebt"]


def entries(facts, tag):
    try:
        u=facts[tag]["units"]
    except Exception: return pd.DataFrame()
    rows=[]
    for unit, arr in u.items():
        for x in arr:
            rows.append({**x,"unit":unit})
    return pd.DataFrame(rows)


def pick(facts, tags):
    best=pd.DataFrame(); best_tag=None; best_end=None
    for t in tags:
        d=entries(facts,t)
        if len(d)==0: continue
        e=pd.to_datetime(d.end,errors="coerce").max()
        if best_end is None or (pd.notna(e) and e>best_end):
            best,best_tag,best_end=d,t,e
    return best,best_tag


def annual(facts, tags):
    best=pd.DataFrame(); best_tag=None; best_end=None
    for t in tags:
        d=entries(facts,t)
        if len(d)==0: continue
        d=d[d.form.astype(str).str.contains("10-K|20-F|40-F")].copy()
        d["start"]=pd.to_datetime(d.start,errors="coerce"); d["end"]=pd.to_datetime(d.end,errors="coerce")
        d["days"]=(d.end-d.start).dt.days
        d=d[(d.days>=330)&(d.days<=400)].dropna(subset=["end","val"]).sort_values("end").drop_duplicates("end",keep="last")
        if len(d)==0: continue
        e=d.end.max()
        if best_end is None or e>best_end:
            best,best_tag,best_end=d,t,e
    return (best.tail(3) if len(best) else best),best_tag


def quarter(facts, tags):
    best=pd.DataFrame(); best_tag=None; best_end=None
    for t in tags:
        d=entries(facts,t)
        if len(d)==0: continue
        d=d[d.form.astype(str).str.contains("10-Q")].copy()
        d["start"]=pd.to_datetime(d.start,errors="coerce"); d["end"]=pd.to_datetime(d.end,errors="coerce")
        d["days"]=(d.end-d.start).dt.days
        d=d[(d.days>=70)&(d.days<=110)].dropna(subset=["end","val"]).sort_values("end").drop_duplicates("end",keep="last")
        if len(d)==0: continue
        e=d.end.max()
        if best_end is None or e>best_end:
            best,best_tag,best_end=d,t,e
    return (best.tail(4) if len(best) else best),best_tag


def inst(facts, tags):
    d,t=pick(facts,tags)
    if len(d)==0: return None,None,None
    d=d[d.end.notna()].copy(); d["end"]=pd.to_datetime(d.end,errors="coerce")
    d=d.sort_values("end").drop_duplicates("end",keep="last")
    if len(d)==0: return None,None,None
    x=d.iloc[-1]; return float(x.val),x.end.date().isoformat(),t


def filing(subs):
    rows=subs.get("filings",{}).get("recent",{})
    for i,form in enumerate(rows.get("form",[])):
        if form in ("10-K","10-Q","20-F","40-F"):
            acc=rows["accessionNumber"][i].replace("-","")
            cik=str(int(subs["cik"])).zfill(10)
            doc=rows["primaryDocument"][i]
            return {"form":form,"filing_date":rows["filingDate"][i],"period":rows["reportDate"][i],
                    "accession":rows["accessionNumber"][i],"url":f"https://www.sec.gov/Archives/edgar/data/{int(subs['cik'])}/{acc}/{doc}"}
    return {}

metrics=[]; valuations=[]; sources=[]
for _,c in co.iterrows():
    tk=c.ticker; facts=json.load(open(DATA/f"{tk}_facts.json"))["facts"].get("us-gaap",{})
    subs=json.load(open(DATA/f"{tk}_subs.json"))
    fil=filing(subs)
    ar,art=annual(facts,REV); aoi,oit=annual(facts,OI); ani,nit=annual(facts,NI); aocf,ot=annual(facts,OCF); acx,cxt=annual(facts,CAPEX); ada,dat=annual(facts,DA); agp,gpt=annual(facts,GP); aeps,ept=annual(facts,EPS)
    cash,endc,ct=inst(facts,CASH); debt,_,dt=inst(facts,DEBT); shs,_,st=inst(facts,["EntityCommonStockSharesOutstanding"]) if False else (None,None,None)
    # shares are in dei
    try:
        de=json.load(open(DATA/f"{tk}_facts.json"))["facts"]["dei"]["EntityCommonStockSharesOutstanding"]["units"]["shares"]
        de=sorted(de,key=lambda x:x.get("end","")); shs=float(de[-1]["val"])
    except Exception: shs=None
    sbc,_,_=inst(facts,SBC)
    # latest annual values by end merge
    def latest(df):
        return float(df.iloc[-1].val) if len(df) else None
    rev=latest(ar); gp=latest(agp); oi=latest(aoi); ni=latest(ani); ocf=latest(aocf); capex=latest(acx); da=latest(ada); eps=latest(aeps)
    fcf=(ocf-capex) if ocf is not None and capex is not None else None
    # annual rows
    for _,r in ar.tail(3).iterrows():
        end=r.end.date().isoformat()
        def match(df):
            if len(df)==0: return None
            z=df[df.end==r.end]
            return float(z.iloc[-1].val) if len(z) else None
        metrics.append({"ticker":tk,"company":c.company,"period_type":"FY","period_end":end,"fiscal_year":end[:4],
                        "revenue":rev if False else match(ar),"gross_profit":match(agp),"operating_income":match(aoi),"net_income":match(ani),
                        "eps_diluted":match(aeps),"ocf":match(aocf),"capex":match(acx),"fcf":(match(aocf)-match(acx)) if match(aocf) is not None and match(acx) is not None else None,
                        "source_tag_revenue":art,"source_tag_ocf":ot,"source_tag_net_income":nit})
    # latest quarter
    qr,qrt=quarter(facts,REV); qni,qnit=quarter(facts,NI); qocf,qot=quarter(facts,OCF)
    if len(qr):
        q=qr.iloc[-1]
        metrics.append({"ticker":tk,"company":c.company,"period_type":"Q","period_end":q.end.date().isoformat(),"fiscal_year":q.end.date().isoformat(),
                        "revenue":float(q.val),"net_income":float(qni.iloc[-1].val) if len(qni) else None,"ocf":float(qocf.iloc[-1].val) if len(qocf) else None,
                        "source_tag_revenue":qrt,"source_tag_net_income":qnit,"source_tag_ocf":qot})
    price=px[px.ticker==tk].iloc[0]
    mcap=price.price*shs if pd.notna(price.price) and shs else None
    ev=(mcap+debt-cash) if mcap and debt is not None and cash is not None else None
    ebitda=(oi+da) if oi is not None and da is not None else None
    row={"ticker":tk,"company":c.company,"cik":c.cik,"industry":c.industry,"price":price.price,"price_date":price.price_date,
         "shares":shs,"market_cap":mcap,"cash":cash,"debt":debt,"net_debt":(debt-cash) if debt is not None and cash is not None else None,
         "revenue_ttm":rev,"gross_profit":gp,"operating_income":oi,"net_income":ni,"eps_diluted":eps,"ocf":ocf,"capex":capex,"fcf":fcf,
         "ebitda_proxy":ebitda,"sbc":sbc,"pe":(mcap/ni) if mcap and ni and ni>0 else None,
         "ps":(mcap/rev) if mcap and rev and rev>0 else None,"ev_ebitda":(ev/ebitda) if ev and ebitda and ebitda>0 else None,
         "ev_fcf":(ev/fcf) if ev and fcf and fcf>0 else None,"fcf_yield":(fcf/mcap) if fcf and mcap else None,
         "net_debt_ebitda":((debt-cash)/ebitda) if debt is not None and cash is not None and ebitda and ebitda>0 else None,
         "filing_form":fil.get("form"),"filing_date":fil.get("filing_date"),"filing_period":fil.get("period"),"filing_url":fil.get("url"),"accession":fil.get("accession"),
         "source":"SEC companyfacts + submissions + yfinance raw close"}
    valuations.append(row); sources.append({"ticker":tk,"company":c.company,"form":fil.get("form"),"period":fil.get("period"),"filing_date":fil.get("filing_date"),"url":fil.get("url"),"accession":fil.get("accession"),"description":"latest 10-K/10-Q in submissions","fields":"revenue, net income, OCF, capex, debt, cash, shares"})
pd.DataFrame(metrics).to_csv(OUT/"financial_metrics.csv",index=False)
pd.DataFrame(valuations).to_csv(OUT/"valuation_comparison.csv",index=False)
pd.DataFrame(sources).to_csv(OUT/"source_register.csv",index=False)
print(len(valuations),len(metrics))
print(pd.DataFrame(valuations)[["ticker","revenue_ttm","net_income","fcf","market_cap","pe","ev_fcf"]].to_string(index=False))
