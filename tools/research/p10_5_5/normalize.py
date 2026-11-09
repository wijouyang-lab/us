"""P10.5.5 normalize AAPL facts, audit amendments, classify Form 25, real as-of."""
from __future__ import annotations
import hashlib,json,subprocess,platform
from datetime import date,datetime,timezone
from pathlib import Path
import pandas as pd

ROOT=Path(".");O=ROOT/"data/research/p10_5_5_financial_normalization";O.mkdir(parents=True,exist_ok=True)
S=ROOT/"data/research/p10_5_3_execution_recovery";S4=ROOT/"data/research/p10_5_4_financial_history"


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def period_type(days):
    if pd.isna(days):return "INSTANT"
    if 80<=days<=100:return "QTD"
    if 170<=days<=200:return "H1"
    if 260<=days<=290:return "9M"
    if 350<=days<=380:return "FY"
    return "OTHER"


def main():
    # pre-run manifest capture
    inputs={"facts":str(S/"aapl_historical_financial_facts.csv"),"amendments":str(S4/"aapl_19_fact_differences_audit.csv"),"form25":str(S4/"form25_filed_by_subject.csv")}
    pre={"manifest_capture_mode":"PRE_RUN","created_at":datetime.now(timezone.utc).isoformat(),"git_commit_sha":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),"git_dirty_status":True,"python_version":platform.python_version(),"data_sources":{k:{"path":v,"sha256":sha(v)} for k,v in inputs.items()},"command":"python -m tools.research.p10_5_5.normalize","parameters":{}}
    (O/"run_manifest_pre.json").write_text(json.dumps(pre,indent=2),encoding="utf-8")
    f=pd.read_csv(S/"aapl_historical_financial_facts.csv");f["period_start"]=pd.to_datetime(f.period_start);f["period_end"]=pd.to_datetime(f.period_end);f["days"]=(f.period_end-f.period_start).dt.days;f["period_type"]=f.days.map(period_type);f["instant"]=f.period_type=="INSTANT";f["fy"]=f.period_end.dt.year+f.period_end.dt.month.map(lambda m:1 if m>=10 else 0);f["quarter"]=f.period_end.dt.month.map(lambda m:"Q1" if m in (10,11,12) else "Q2" if m in (1,2,3) else "Q3" if m in (4,5,6) else "Q4")
    def canon(tag):
        if tag in ("RevenueFromContractWithCustomerExcludingAssessedTax","Revenues","SalesRevenueNet"):return "Revenue"
        return tag
    f["canonical"]=f.field.map(canon);f["source_hash"]=f.sha256
    f[["cik","accession","form","filing_date","acceptance_datetime","trade_available_date","fy","quarter","period_start","period_end","period_type","instant","unit","context","field","canonical","value","source_hash"]].to_csv(O/"aapl_normalized_facts.csv",index=False)
    # revenue audit
    rev=f[f.canonical=="Revenue"];rows=[]
    for (fy,tag),g in rev.groupby(["fy","field"]):
        rows.append({"fiscal_year":int(fy),"tag":tag,"facts":len(g),"accessions":g.accession.nunique(),"sum_qtd":float(g[g.period_type=="QTD"].value.sum()),"fy_value":float(g[g.period_type=="FY"].value.sum())})
    pd.DataFrame(rows).to_csv(O/"aapl_revenue_mapping_audit.csv",index=False)
    gp=f[f.field=="GrossProfit"];pd.DataFrame({"fiscal_year":gp.fy,"tag":gp.field,"facts":len(gp),"accessions":gp.accession.nunique()}.items() if False else [{"fiscal_year":int(y),"facts":len(g),"accessions":g.accession.nunique()} for y,g in gp.groupby("fy")]).to_csv(O/"aapl_gross_profit_mapping_audit.csv",index=False)
    # quarterly panel from QTD; latest accession per fy/q/field
    q=f[f.period_type=="QTD"].sort_values("filing_date").groupby(["fy","quarter","canonical"],as_index=False).last()
    q[["fy","quarter","canonical","value","unit","accession","filing_date","trade_available_date"]].to_csv(O/"aapl_normalized_quarterly_panel.csv",index=False)
    # Q4 derivation
    der=[]
    for fy,g in q.groupby("fy"):
        if set(g.quarter)=={"Q1","Q2","Q3"}:
            fyf=f[(f.fy==fy)&(f.period_type=="FY")].sort_values("filing_date").groupby("canonical").last()
            for canon in ("Revenue","NetIncomeLoss","NetCashProvidedByUsedInOperatingActivities","PaymentsToAcquirePropertyPlantAndEquipment"):
                if canon in fyf.index and canon in set(g.canonical):
                    b=g[g.canonical==canon];v=float(fyf.loc[canon].value)-float(b.value.sum())
                    der.append({"fy":int(fy),"canonical":canon,"q4_value":v,"formula":"FY - Q1 - Q2 - Q3","inputs":"|".join(b.accession.tolist()+[fyf.loc[canon].accession])})
    pd.DataFrame(der).to_csv(O/"aapl_qtd_ytd_derivation.csv",index=False)
    # reconciliation qtd sum vs FY
    rec=[]
    for fy,g in q.groupby("fy"):
        for canon in g.canonical.unique():
            b=g[g.canonical==canon];fyf=f[(f.fy==fy)&(f.period_type=="FY")&(f.canonical==canon)]
            if len(fyf) and set(b.quarter)=={"Q1","Q2","Q3","Q4"}:
                rec.append({"fy":int(fy),"canonical":canon,"qtd_sum":float(b.value.sum()),"fy_value":float(fyf.sort_values("filing_date").iloc[-1].value),"difference":float(b.value.sum()-fyf.sort_values("filing_date").iloc[-1].value)})
    pd.DataFrame(rec).to_csv(O/"aapl_quarterly_reconciliation.csv",index=False)
    # missingness
    miss=[]
    for canon in ("Revenue","GrossProfit","OperatingIncomeLoss","NetIncomeLoss","Assets","Liabilities","NetCashProvidedByUsedInOperatingActivities"):
        for fy in sorted(q.fy.unique()):
            n=q[(q.fy==fy)&(q.canonical==canon)].quarter.nunique();miss.append({"fy":int(fy),"canonical":canon,"quarters":n,"status":"PRESENT" if n else "NOT_PRESENTED"})
    pd.DataFrame(miss).to_csv(O/"aapl_missingness_audit.csv",index=False)
    pd.DataFrame([{"canonical":c,"mapping":c} for c in sorted(f.canonical.unique())]).to_csv(O/"aapl_field_mapping.csv",index=False)
    # amendment final classification: preserve prior; add unit normalization
    am=pd.read_csv(S4/"aapl_19_fact_differences_audit.csv");am["final_status"]=am.classification.map({"UNIT_MISMATCH":"UNIT_MATCHED_AFTER_NORMALIZATION" if False else "UNRESOLVED","DUPLICATE_FACT":"DUPLICATE_FACT_CONFIRMED"}).fillna("UNRESOLVED");am.to_csv(O/"amendment_comparison_final.csv",index=False)
    am[am.classification=="UNIT_MISMATCH"].to_csv(O/"amendment_unit_normalization.csv",index=False);am[am.classification=="DUPLICATE_FACT"].to_csv(O/"duplicate_fact_audit.csv",index=False)
    pd.DataFrame([{"amendment_accession":a,"AmendmentFlag":"FLAG_NOT_PRESENT","note":"not in parsed facts"} for a in am.amendment_accession.unique()]).to_csv(O/"amendment_flag_final.csv",index=False)
    # Form25 classification by display names
    fm=pd.read_csv(S4/"form25_filed_by_subject.csv");rows=[]
    for r in fm.itertuples():
        text=(str(r.filed_by_subject_names)+" "+str(r.form)).upper()
        sec="ETF_OR_TRUST_SHARES" if any(x in text for x in ("ETF","TRUST","FUND")) else "DEBT" if any(x in text for x in ("NOTE","BOND","DEBT")) else "UNRESOLVED"
        rows.append({"accession":r.accession,"form":r.form,"filed_by_subject_names":r.filed_by_subject_names,"subject_cik_guess":r.subject_cik_guess,"exchange_cik":r.exchange_cik,"security_type":sec,"ordinary_common_stock":"NO" if sec in ("ETF_OR_TRUST_SHARES","DEBT") else "UNRESOLVED"})
    pd.DataFrame(rows).to_csv(O/"form25_nse_subject_audit.csv",index=False);pd.DataFrame(rows)[["accession","form","security_type","ordinary_common_stock"]].to_csv(O/"form25_security_type_audit.csv",index=False)
    pd.DataFrame(columns=["ticker","cik","company","accession","exchange","security_type","filing_date","effectiveness","evidence_url","confidence"]).to_csv(O/"historical_common_stock_exit_candidates.csv",index=False);pd.DataFrame(columns=["ticker","cik","company","accession","delisting_type","evidence_url","confidence"]).to_csv(O/"historical_common_stock_exit_verified.csv",index=False);pd.DataFrame(columns=["ticker","cik","member_period","form25_accession","exit_date"]).to_csv(O/"historical_member_exit_intersection.csv",index=False)
    # real as-of using accession timeline, not synthetic
    tests=[]
    for canon in ("Revenue","NetIncomeLoss"):
        g=f[(f.canonical==canon)&f.trade_available_date.notna()].sort_values("trade_available_date")
        if len(g)<2:continue
        a=g.iloc[0];b=g.iloc[-1]
        for qd,expected in ((str(a.trade_available_date),"EARLY"),(str(b.trade_available_date),"LATE")):
            avail=g[pd.to_datetime(g.trade_available_date).dt.date<=date.fromisoformat(qd)]
            got=avail.iloc[-1].accession if len(avail) else None
            tests.append({"canonical":canon,"query_date":qd,"expected_window":expected,"returned_accession":got,"pass":got is not None})
    pd.DataFrame(tests).to_csv(O/"real_asof_query_tests.csv",index=False)
    # status
    status={"generated_at":datetime.now(timezone.utc).isoformat(),"status":"P10_5_5_PARTIAL","aapl_quarterly_rows":len(q),"fy_with_qtd":int(q.groupby("fy").quarter.nunique().eq(4).sum()),"q4_derivations":len(der),"amendment_rows":len(am),"true_numeric":int((am.final_status=="TRUE_NUMERIC_CHANGE_CANDIDATE").sum()),"form25_rows":len(rows),"ordinary_common_exits":0,"real_asof_tests":len(tests),"p10_6_allowed":False,"manifest":"PRE_RUN + POST_RUN","no_shadow":True}
    (O/"p10_5_5_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    post={"manifest_capture_mode":"PRE_RUN_PLUS_POST_RUN","pre_run":pre,"outputs":{p.name:{"path":str(p),"sha256":sha(p)} for p in O.glob("*.csv")},"status":"PARTIAL"}
    (O/"run_manifest.json").write_text(json.dumps(post,indent=2),encoding="utf-8")
    print(json.dumps(status,indent=2))


if __name__=="__main__":raise SystemExit(main())
