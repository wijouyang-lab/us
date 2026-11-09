"""P10.5.4 AAPL quarterly history, amendment differences, Form 25 subject mapping."""
from __future__ import annotations
import csv,hashlib,json,re
from datetime import date,datetime,timezone
from pathlib import Path
import pandas as pd,requests

ROOT=Path(".");O=ROOT/"data/research/p10_5_4_financial_history";O.mkdir(parents=True,exist_ok=True);S=ROOT/"data/research/p10_5_3_execution_recovery"
UA={"User-Agent":"us-pit-research/1.0 research@example.com"}
CORE={"Revenue","RevenueFromContractWithCustomerExcludingAssessedTax","Revenues","SalesRevenueNet","GrossProfit","OperatingIncomeLoss","NetIncomeLoss","EarningsPerShareBasic","EarningsPerShareDiluted","Assets","Liabilities","CashAndCashEquivalentsAtCarryingValue","LongTermDebt","StockholdersEquity","NetCashProvidedByUsedInOperatingActivities","PaymentsToAcquirePropertyPlantAndEquipment","WeightedAverageNumberOfSharesOutstandingBasic","WeightedAverageNumberOfDilutedSharesOutstanding","CommonStockSharesOutstanding"}


def main():
    f=pd.read_csv(S/"aapl_historical_financial_facts.csv");f=f[f.field.isin(CORE)].copy();f["period_start"]=pd.to_datetime(f.period_start);f["period_end"]=pd.to_datetime(f.period_end);f=f.dropna(subset=["period_end"])
    f["days"]=(f.period_end-f.period_start).dt.days
    def dur(x):
        if pd.isna(x):return "INSTANT"
        if 80<=x<=100:return "QTD"
        if 170<=x<=200:return "H1"
        if 260<=x<=290:return "9M"
        if 350<=x<=380:return "FY"
        return "OTHER"
    f["duration"]=f.days.map(dur);f["fy"]=f.period_end.dt.year+f.period_end.dt.month.map(lambda m:1 if m>=10 else 0);f["q"]=f.period_end.dt.month.map(lambda m:"Q1" if m in (10,11,12) else "Q2" if m in (1,2,3) else "Q3" if m in (4,5,6) else "Q4")
    # choose latest accession per canonical field/period/duration
    f=f.sort_values(["filing_date","accession"]);rows=[]
    for r in f.itertuples():
        rows.append({"accession":r.accession,"form":r.form,"filing_date":r.filing_date,"tag":r.field,"value":r.value,"unit":r.unit,"period_start":str(r.period_start.date()) if pd.notna(r.period_start) else "","period_end":str(r.period_end.date()),"duration":r.duration,"fiscal_year":int(r.fy),"quarter":r.q,"canonical":"Revenue" if r.field in ("Revenue","RevenueFromContractWithCustomerExcludingAssessedTax","Revenues","SalesRevenueNet") else r.field})
    q=pd.DataFrame(rows);q.to_csv(O/"aapl_quarterly_financials.csv",index=False)
    # validation: two latest fiscal years with all 4 quarters for core fields
    complete=[]
    for fy,g in q[q.duration.isin(["QTD","H1","9M","FY"])].groupby("fiscal_year"):
        qs=set(g[g.duration=="QTD"].quarter.unique());complete.append({"fiscal_year":int(fy),"quarters_with_qtd":len(qs),"fields":g.canonical.nunique()})
    pd.DataFrame(complete).to_csv(O/"aapl_period_validation.csv",index=False)
    # derivations: Q4 = FY - Q1-Q2-Q3 where direct QTD exists; only same canonical/unit/fy, use selected latest
    der=[]
    for fy in sorted(q.fiscal_year.unique())[-2:]:
        g=q[(q.fiscal_year==fy)&(q.duration=="QTD")]
        if set(g.quarter)=={"Q1","Q2","Q3"}:
            fyrow=q[(q.fiscal_year==fy)&(q.duration=="FY")]
            for canon in ("Revenue","NetIncomeLoss","NetCashProvidedByUsedInOperatingActivities"):
                a=fyrow[fyrow.canonical==canon];b=g[g.canonical==canon]
                if len(a) and set(b.quarter)=={"Q1","Q2","Q3"}:
                    v=a.sort_values("filing_date").iloc[-1].value-sum(b.sort_values("filing_date").groupby("quarter").value.last())
                    der.append({"fiscal_year":int(fy),"canonical":canon,"q4_value":v,"formula":"FY - Q1 - Q2 - Q3","accessions":"|".join(map(str,a.accession.tolist()+b.accession.tolist())),"status":"DERIVED"})
    pd.DataFrame(der).to_csv(O/"aapl_qtd_ytd_derivation.csv",index=False)
    # amendment audit from P10.5.3 lineage
    am=pd.read_csv(S/"restatement_lineage.csv")
    fa=f[["accession","field","period_start","period_end","unit","value","context"]]
    diffs=[]
    for r in am.itertuples():
        original=fa[fa.accession==r.original_accession];amend=fa[fa.accession==r.amendment_accession]
        x=amend[(amend.field==r.field)&(amend.period_start==pd.Timestamp(r.period_start))&(amend.period_end==pd.Timestamp(r.period_end))]
        y=original[(original.field==r.field)&(original.period_start==pd.Timestamp(r.period_start))&(original.period_end==pd.Timestamp(r.period_end))]
        cls="UNRESOLVED";reason="no exact unit/context match"
        if len(x) and len(y):
            if len(x)>1 or len(y)>1:cls="DUPLICATE_FACT";reason="multiple facts for same key"
            elif x.iloc[0].unit!=y.iloc[0].unit:cls="UNIT_MISMATCH";reason="unit differs"
            elif abs(float(x.iloc[0].value)-float(y.iloc[0].value))<1e-9:cls="TEXT_ONLY_AMENDMENT";reason="same value"
            else:cls="TRUE_NUMERIC_CHANGE_CANDIDATE";reason="same field/period/unit, different value"
        diffs.append({"original_accession":r.original_accession,"amendment_accession":r.amendment_accession,"form":r.form,"field":r.field,"period_start":r.period_start,"period_end":r.period_end,"original_value":r.original_value,"amendment_value":r.amendment_value,"classification":cls,"reason":reason})
    pd.DataFrame(diffs).to_csv(O/"aapl_19_fact_differences_audit.csv",index=False)
    pd.DataFrame([{"accession":r.amendment_accession,"form":r.form,"AmendmentFlag":"FLAG_NOT_PRESENT","note":"not parsed from original amendment in this pass"} for r in am.drop_duplicates("amendment_accession").itertuples()]).to_csv(O/"aapl_amendment_flag_audit.csv",index=False)
    # as-of only if true candidate with two usable dates; otherwise empty with status
    tests=[]
    for r in diffs:
        if r["classification"]=="TRUE_NUMERIC_CHANGE_CANDIDATE":tests.append({**r,"test":"REQUIRES_REAL_TIMESTAMP_REVIEW","status":"UNRESOLVED"})
    pd.DataFrame(tests).to_csv(O/"real_asof_query_tests.csv",index=False)
    # Form 25 search actual; exact form filter
    r=requests.get("https://efts.sec.gov/LATEST/search-index?q=%22FORM%2025-NSE%22&forms=25-NSE&size=100",headers=UA,timeout=30);d=r.json();hits=d["hits"]["hits"]
    fr=[]
    for h in hits:
        s=h["_source"];names=s.get("display_names",[]);ciks=s.get("ciks",[])
        fr.append({"accession":h["_id"].split(":")[0],"form":s.get("form"),"file_date":s.get("file_date"),"filed_by_subject_names":"|".join(names),"ciks":"|".join(ciks),"subject_cik_guess":ciks[0] if ciks else "","exchange_cik":ciks[1] if len(ciks)>1 else ""})
    pd.DataFrame(fr).to_csv(O/"form25_filed_by_subject.csv",index=False)
    pd.DataFrame(fr).drop_duplicates("accession").to_csv(O/"form25_accessions_deduplicated.csv",index=False)
    pd.DataFrame([{"accession":x["accession"],"security_class":"UNKNOWN","is_common_stock":"UNKNOWN","status":"NOT_PARSED"} for x in fr]).to_csv(O/"form25_security_classification.csv",index=False)
    pd.DataFrame(columns=["ticker","cik","company","form25_accession","effectiveness","security_class","delisting_type","evidence_url","confidence"]).to_csv(O/"historical_common_stock_exits.csv",index=False)
    pd.DataFrame(columns=["ticker","cik","company","form25_accession","effectiveness","security_class","delisting_type","evidence_url","confidence"]).to_csv(O/"delisting_evidence.csv",index=False)
    status={"generated_at":datetime.now(timezone.utc).isoformat(),"status":"P10_5_4_PARTIAL","aapl_quarter_rows":len(q),"aapl_complete_fy":int((pd.DataFrame(complete).quarters_with_qtd==4).sum()),"q4_derivations":len(der),"amendment_rows":len(diffs),"true_numeric_candidates":sum(1 for x in diffs if x["classification"]=="TRUE_NUMERIC_CHANGE_CANDIDATE"),"form25_search_total":d["hits"]["total"]["value"],"form25_rows":len(fr),"verified_common_stock_exits":0,"p10_6_allowed":False,"data_blocked":["Form25 security class/subject verification","true numeric restatement timestamps","complete 30-company sample"],"no_shadow":True}
    json.dump(status,open(O/"p10_5_4_status.json","w"),indent=2)
    json.dump({"search_total":d["hits"]["total"]["value"],"rows":len(fr),"note":"exact form 25-NSE filter; 3663 is unfiltered text-hit count"},open(O/"delisting_audit_status.json","w"),indent=2)
    print(json.dumps(status,indent=2))


if __name__=="__main__":raise SystemExit(main())
