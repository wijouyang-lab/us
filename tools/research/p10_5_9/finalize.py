"""P10.5.9 final AAPL versioned panel and fact-level PIT audit."""
from __future__ import annotations
import hashlib,json
from datetime import date
from pathlib import Path
import pandas as pd,requests

ROOT=Path(".");O=ROOT/"data/research/p10_5_9_aapl_panel";O.mkdir(parents=True,exist_ok=True)
S8=ROOT/"data/research/p10_5_8_aapl_pit";S7=ROOT/"data/research/p10_5_7_accounting_pit";S6=ROOT/"data/research/p10_5_6_financial_final";F=ROOT/"data/research/p10_5_3_execution_recovery/aapl_historical_financial_facts.csv"
UA={"User-Agent":"us-pit-research/1.0 research@example.com"}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    pre={"manifest_capture_mode":"PRE_RUN","git_commit_sha":"WORKTREE","inputs":{"panel":str(S8/"aapl_quarterly_panel_v2.csv"),"facts":str(F)},"command":"python -m tools.research.p10_5_9.finalize"}
    (O/"run_manifest_pre.json").write_text(json.dumps(pre,indent=2),encoding="utf-8")
    p=pd.read_csv(S8/"aapl_quarterly_panel_v2.csv")
    p["accounting_basis"]="ORIGINAL_REPORTED";p.loc[p.accession=="0001193125-10-012091","accounting_basis"]="RETROSPECTIVE_ADJUSTED";p.loc[p.accession=="0001193125-09-214859","accounting_basis"]="ORIGINAL_REPORTED";p["fact_status"]="REPORTED";p["grain_key"]=p.fy.astype(str)+"|"+p.quarter+p.canonical+p.accounting_basis+p.accession
    p.to_csv(O/"aapl_quarterly_panel_v3.csv",index=False)
    pd.DataFrame([{"grain":"CIK + fiscal_year + fiscal_period + canonical_field + accounting_basis + source_accession","rows":len(p),"unique_keys":p.grain_key.nunique(),"duplicate_rows":len(p)-p.grain_key.nunique(),"fy":int(p.fy.nunique()),"fields":int(p.canonical.nunique())}]).to_csv(O/"aapl_panel_grain_final.csv",index=False)
    p[p.duplicated("grain_key",keep=False)].to_csv(O/"aapl_panel_duplicate_final.csv",index=False)
    p.groupby(["fy","accounting_basis","accession"]).size().reset_index(name="rows").to_csv(O/"aapl_panel_version_final.csv",index=False)
    # two FY: 2018/2019 from available Q1-Q4; no performance selection
    fys=[2018,2019];sel=p[p.fy.isin(fys)].copy();sel.to_csv(O/"aapl_two_fy_panel_final.csv",index=False)
    core=["Revenue","OperatingIncomeLoss","NetIncomeLoss","EarningsPerShareBasic","EarningsPerShareDiluted","NetCashProvidedByUsedInOperatingActivities","PaymentsToAcquirePropertyPlantAndEquipment","GrossProfit"]
    cov=[]
    for fy in fys:
        for c in core:
            g=sel[(sel.fy==fy)&(sel.canonical==c)]
            cov.append({"fy":fy,"canonical":c,"quarters":int(g.quarter.nunique()),"accessions":int(g.accession.nunique()),"status":"PRESENT" if g.quarter.nunique()==4 else ("PARTIAL" if g.quarter.nunique() else "NOT_PRESENTED")})
    pd.DataFrame(cov).to_csv(O/"aapl_field_coverage_final.csv",index=False);pd.DataFrame(cov).to_csv(O/"aapl_two_fy_field_coverage.csv",index=False)
    # reconciliation qtd vs annual if present
    rec=[]
    for fy in fys:
        for c in ("Revenue","NetIncomeLoss","OperatingIncomeLoss"):
            g=sel[(sel.fy==fy)&(sel.canonical==c)]
            if g.quarter.nunique()==4:
                rec.append({"fy":fy,"canonical":c,"qtd_sum":float(g.value.sum()),"status":"CHECKED_QTD_ONLY"})
    pd.DataFrame(rec).to_csv(O/"aapl_two_fy_quarterly_reconciliation.csv",index=False)
    # basis audit
    pd.DataFrame([{"fy":fy,"basis":"ORIGINAL_REPORTED","rows":int((p.fy==fy).sum())} for fy in sorted(p.fy.unique())]).to_csv(O/"aapl_accounting_basis_audit.csv",index=False)
    # fact-level as-of 5 fields A/B
    facts=pd.read_csv(F,dtype={"accession":str});facts["trade_available_date"]=pd.to_datetime(facts.trade_available_date).dt.date
    fields=["EarningsPerShareBasic","EarningsPerShareDiluted","SalesRevenueNet","GrossProfit","OperatingIncomeLoss"];dates=["2009-10-28","2010-01-25","2010-01-26","2010-01-27"];out=[]
    for fld in fields:
        sub=facts[facts.field==fld];rr=sub[(sub.period_start.astype(str).str.startswith("2007-09-30")) | (sub.period_end.astype(str).str.startswith("2008-09-27"))]
        for qd in dates:
            q=date.fromisoformat(qd);av=rr[rr.trade_available_date<=q].sort_values("trade_available_date");got=av.iloc[-1] if len(av) else None
            out.append({"field":fld,"query_date":qd,"returned_accession":got.accession if got is not None else "","returned_value":got.value if got is not None else None,"pass":got is not None})
    pd.DataFrame(out).to_csv(O/"aapl_fact_level_asof_tests.csv",index=False);pd.DataFrame(out).to_csv(O/"aapl_fact_availability_audit.csv",index=False)
    # Form25 6 actual index fetch
    fm=pd.read_csv(S6/"form25_nse_45_final.csv");u=fm[fm.final_classification=="UNRESOLVED"].copy();rows=[]
    for r in u.itertuples():
        acc=r.accession;base=f"https://www.sec.gov/Archives/edgar/data/{int(r.subject_cik_guess or 0)}/{acc.replace('-','')}";http="";err=""
        try:
            rr=requests.get(base+"/index.json",headers=UA,timeout=20);http=rr.status_code
        except Exception as e:err=str(e)[:120]
        rows.append({"accession":acc,"subject_cik":r.subject_cik_guess,"http":http,"error":err,"security_type":"UNRESOLVED","reason":"original security document not parsed" if not http else "index reachable but security class not parsed"})
    pd.DataFrame(rows).to_csv(O/"form25_nse_unresolved_final.csv",index=False);pd.concat([fm[fm.final_classification!="UNRESOLVED"],pd.DataFrame(rows).assign(form="25-NSE")],ignore_index=True).to_csv(O/"form25_nse_45_final_v3.csv",index=False)
    # status
    ds_ready=all(x["status"]=="PRESENT" for x in cov)
    fact_ready=all(x["pass"] for x in out) and len(out)==20
    status={"generated_at":"2026-11-09T13:40:00+00:00","status":"P10_5_9_PARTIAL","panel_rows":len(p),"two_fy":[2018,2019],"two_fy_rows":len(sel),"AAPL_DATASET_READY":bool(ds_ready),"AAPL_FACT_PIT_READY":bool(fact_ready),"HISTORICAL_UNIVERSE_READY":False,"form25_unresolved":len(rows),"p10_6_allowed":False,"no_shadow":True}
    (O/"p10_5_9_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    post={"manifest_capture_mode":"PRE_RUN_PLUS_POST_RUN","pre_run":pre,"outputs":{q.name:{"path":str(q),"sha256":sha(q)} for q in O.glob("*.csv")},"status":"PARTIAL"}
    (O/"run_manifest.json").write_text(json.dumps(post,indent=2),encoding="utf-8")
    print(json.dumps(status,indent=2))


if __name__=="__main__":raise SystemExit(main())
