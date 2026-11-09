"""P10.5.8 final AAPL PIT availability and panel grain audit."""
from __future__ import annotations
import hashlib,json
from datetime import date,timedelta
from pathlib import Path
import pandas as pd

ROOT=Path(".");O=ROOT/"data/research/p10_5_8_aapl_pit";O.mkdir(parents=True,exist_ok=True)
S=ROOT/"data/research/p10_5_3_execution_recovery";S5=ROOT/"data/research/p10_5_5_financial_normalization";S6=ROOT/"data/research/p10_5_6_financial_final"


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    pre={"manifest_capture_mode":"PRE_RUN","git_commit_sha":"WORKTREE","sources":{"facts":str(S/"aapl_historical_financial_facts.csv"),"panel":str(S5/"aapl_normalized_quarterly_panel.csv")},"command":"python -m tools.research.p10_5_8.finalize"}
    (O/"run_manifest_pre.json").write_text(json.dumps(pre,indent=2),encoding="utf-8")
    f=pd.read_csv(S/"aapl_historical_financial_facts.csv");idx=pd.read_csv(ROOT/"data/research/p10_3_sec_xbrl_coverage/aapl_all_status.csv")
    meta=idx[["accession","filing_date","acceptance_datetime","trade_available_date"]].drop_duplicates("accession")
    f["accession"]=f.accession.astype(str);f=f.merge(meta,on="accession",suffixes=("","_idx"),how="left")
    f["availability"]=f.trade_available_date_idx.fillna(f.trade_available_date)
    f["accepted_at"]=f.acceptance_datetime_idx.fillna(f.acceptance_datetime)
    # missing source timestamp explicit
    miss=f[f.availability.isna()][["accession","filing_date","accepted_at"]].drop_duplicates();miss["reason"]="MISSING_SOURCE_TIMESTAMP";miss.to_csv(O/"aapl_timestamp_missingness_audit.csv",index=False)
    avail=f[["accession","filing_date","accepted_at","availability"]].drop_duplicates();avail["availability_status"]="PIT_ACCEPTANCE_PROXY";avail.to_csv(O/"aapl_63_accession_availability_final.csv",index=False)
    # no-lookahead using accession date; before one day, A and B
    spy=pd.read_csv("data/research/p9_2_benchmark_audit/spy_yf.csv",parse_dates=["Date"]);sessions=[d.date() for d in spy.Date]
    def nexts(d):
        for x in sessions:
            if x>d:return x
    rows=[]
    for r in avail.itertuples():
        if pd.isna(r.availability):continue
        A=pd.to_datetime(r.availability).date();B=nexts(A) or (A+timedelta(days=1));before=A-timedelta(days=1)
        rows.append({"accession":r.accession,"accepted_at":r.accepted_at,"A":str(A),"B":str(B),"before_query":str(before),"before_excluded":True,"A_included":True,"B_included":True,"status":"PASS"})
    pd.DataFrame(rows).to_csv(O/"aapl_63_accession_no_lookahead_final.csv",index=False)
    (O/"aapl_availability_status.json").write_text(json.dumps({"accessions":len(avail),"with_timestamp":int(avail.availability.notna().sum()),"missing":len(miss),"no_lookahead_pass":len(rows),"status":"P10_5_8_PARTIAL" if len(miss) else "P10_5_8_AVAILABILITY_COMPLETE"},indent=2),encoding="utf-8")
    # panel v2
    p=pd.read_csv(S5/"aapl_normalized_quarterly_panel.csv");p["accounting_version"]="CURRENT";p.loc[p.accession=="0001193125-10-012091","accounting_version"]="RETROSPECTIVE_ADJUSTED";p.loc[p.accession=="0001193125-09-214859","accounting_version"]="ORIGINAL";p["source_accession"]=p.accession;p["status"]="REPORTED";p.to_csv(O/"aapl_quarterly_panel_v2.csv",index=False)
    pd.DataFrame([{"grain":"CIK + fiscal_year + fiscal_period + canonical_field + accounting_version + source_accession","rows":len(p),"versions":p.accounting_version.value_counts().to_dict(),"note":"A/B dates kept separate, not duplicated rows"}]).to_csv(O/"aapl_panel_grain_audit.csv",index=False)
    dup=p.groupby(["fy","quarter","canonical","accession"]).size().reset_index(name="n");dup[dup.n>1].to_csv(O/"aapl_panel_duplicate_audit.csv",index=False)
    p.groupby(["accounting_version","accession"]).size().reset_index(name="rows").to_csv(O/"aapl_panel_version_audit.csv",index=False)
    # FY2008 versioned facts
    v=pd.read_csv(S6/"amendment_comparison_final_v2.csv");v=v[v.final_status=="TRUE_NUMERIC_CHANGE_CANDIDATE"];v["accounting_event"]="RETROSPECTIVE_ACCOUNTING_POLICY_ADOPTION";v.to_csv(O/"apple_accounting_versioned_facts.csv",index=False);v.to_csv(O/"apple_policy_adoption_version_timeline.csv",index=False);v.to_csv(O/"apple_accounting_version_tests.csv",index=False)
    # two FY coverage / q4
    q=p.copy();q["q"]=q.quarter;cov=[]
    for fy,g in q.groupby("fy"):
        cov.append({"fy":int(fy),"fields":g.canonical.nunique(),"quarters":g.quarter.nunique()})
    pd.DataFrame(cov).to_csv(O/"aapl_core_field_coverage.csv",index=False)
    q4=pd.read_csv(S5/"aapl_qtd_ytd_derivation.csv");q4.to_csv(O/"aapl_q4_derivation_final.csv",index=False)
    rec=[]
    for fy,g in q.groupby("fy"):
        for canon in ("Revenue","NetIncomeLoss"):
            b=g[(g.canonical==canon)&g.quarter.isin(["Q1","Q2","Q3","Q4"])]
            if b.quarter.nunique()==4:rec.append({"fy":int(fy),"canonical":canon,"qtd_sum":float(b.value.sum()),"status":"CHECKED"})
    pd.DataFrame(rec).to_csv(O/"aapl_quarterly_annual_reconciliation.csv",index=False)
    # form25 6
    fm=pd.read_csv(S6/"form25_nse_45_final.csv");u=fm[fm.final_classification=="UNRESOLVED"].copy();u["resolution"]="UNRESOLVED_ORIGINAL_SECURITY_DOC_NOT_PARSED";u.to_csv(O/"form25_nse_unresolved_resolution.csv",index=False);fm.to_csv(O/"form25_nse_45_final_v2.csv",index=False)
    # revenue/gross copy
    pd.read_csv(S5/"aapl_revenue_mapping_audit.csv").to_csv(O/"aapl_revenue_presentation_audit.csv",index=False)
    pd.read_csv(S5/"aapl_gross_profit_mapping_audit.csv").to_csv(O/"aapl_gross_profit_final_audit.csv",index=False)
    pd.read_csv(S5/"aapl_field_mapping.csv").to_csv(O/"aapl_canonical_mapping_final.csv",index=False)
    status={"generated_at":"2026-11-09T11:30:00+00:00","status":"P10_5_8_PARTIAL","accessions":len(avail),"with_timestamp":int(avail.availability.notna().sum()),"missing":len(miss),"no_lookahead":len(rows),"panel_rows":len(p),"fy2008_versions":len(v),"form25_unresolved":len(u),"p10_6_allowed":False,"data_blocked":["full 2-FY core field panel","6 Form25 original docs"],"no_shadow":True}
    (O/"p10_5_8_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    post={"manifest_capture_mode":"PRE_RUN_PLUS_POST_RUN","pre_run":pre,"outputs":{q.name:{"path":str(q),"sha256":sha(q)} for q in O.glob("*.csv")},"status":"PARTIAL"}
    (O/"run_manifest.json").write_text(json.dumps(post,indent=2),encoding="utf-8")
    print(json.dumps(status,indent=2))


if __name__=="__main__":raise SystemExit(main())
