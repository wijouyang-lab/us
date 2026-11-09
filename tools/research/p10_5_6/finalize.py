"""P10.5.6 finalize unit normalization and real amendment version checks."""
from __future__ import annotations
import hashlib,json
from datetime import date
from pathlib import Path
import pandas as pd

O=Path("data/research/p10_5_6_financial_final");O.mkdir(parents=True,exist_ok=True)
S=Path("data/research/p10_5_5_financial_normalization");F=Path("data/research/p10_5_3_execution_recovery/aapl_historical_financial_facts.csv")


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def norm_unit(u):
    u=str(u)
    if "USD_per_shares" in u or "USDperShare" in u:return "USD/share"
    if "USD" in u:return "USD"
    if u.lower()=="shares":return "shares"
    return u


def main():
    am=pd.read_csv(S/"amendment_comparison_final.csv");f=pd.read_csv(F);f["unit_norm"]=f.unit.map(norm_unit);f["period_start"]=pd.to_datetime(f.period_start);f["period_end"]=pd.to_datetime(f.period_end)
    out=[]
    for r in am.itertuples():
        a=f[(f.accession==r.amendment_accession)&(f.field==r.field)&(f.period_start==pd.Timestamp(r.period_start))&(f.period_end==pd.Timestamp(r.period_end))]
        o=f[(f.accession==r.original_accession)&(f.field==r.field)&(f.period_start==pd.Timestamp(r.period_start))&(f.period_end==pd.Timestamp(r.period_end))]
        if r.classification=="DUPLICATE_FACT":cls="DUPLICATE_FACT"
        elif len(a)==0 or len(o)==0:cls="CONTEXT_MISMATCH"
        elif a.iloc[0].unit_norm!=o.iloc[0].unit_norm:cls="UNIT_INCOMPATIBLE"
        elif abs(float(a.iloc[0].value)-float(o.iloc[0].value))<1e-9:cls="NORMALIZED_EQUAL"
        else:cls="TRUE_NUMERIC_CHANGE_CANDIDATE"
        out.append({"original_accession":r.original_accession,"amendment_accession":r.amendment_accession,"form":r.form,"field":r.field,"period_start":r.period_start,"period_end":r.period_end,"original_value":r.original_value,"amendment_value":r.amendment_value,"original_unit":o.iloc[0].unit if len(o) else "","amendment_unit":a.iloc[0].unit if len(a) else "","normalized_unit":a.iloc[0].unit_norm if len(a) else "","final_status":cls})
    df=pd.DataFrame(out);df.to_csv(O/"amendment_unit_normalization_final.csv",index=False);df.to_csv(O/"amendment_comparison_final_v2.csv",index=False)
    # real as-of for true numeric candidates: original filing date vs amendment filing date
    tests=[]
    for r in df[df.final_status=="TRUE_NUMERIC_CHANGE_CANDIDATE"].itertuples():
        ob=f[f.accession==r.original_accession].iloc[0];ab=f[f.accession==r.amendment_accession].iloc[0]
        for qd,expected in ((str(ob.trade_available_date),"BEFORE_AMENDMENT"),(str(ab.trade_available_date),"AFTER_AMENDMENT")):
            avail=f[(f.field==r.field)&(f.period_start==pd.Timestamp(r.period_start))&(f.period_end==pd.Timestamp(r.period_end))&(f.trade_available_date.notna())&(pd.to_datetime(f.trade_available_date).dt.date<=date.fromisoformat(qd))]
            got=avail.sort_values("trade_available_date").iloc[-1] if len(avail) else None
            tests.append({"field":r.field,"period_start":r.period_start,"period_end":r.period_end,"query_date":qd,"expected":expected,"returned_accession":got.accession if got is not None else "","returned_value":got.value if got is not None else None})
    pd.DataFrame(tests).to_csv(O/"real_asof_query_tests.csv",index=False);pd.DataFrame(tests).to_csv(O/"aapl_asof_full_accession_tests.csv",index=False)
    # Form25 final preserve 45; no ordinary Form25 this pass
    fm=pd.read_csv(S/"form25_nse_subject_audit.csv");fm["final_classification"]=fm.security_type.map({"ETF_OR_TRUST_SHARES":"ETF_OR_TRUST_SHARES","DEBT":"DEBT"}).fillna("UNRESOLVED");fm.to_csv(O/"form25_nse_45_final.csv",index=False);fm[fm.final_classification=="UNRESOLVED"].to_csv(O/"form25_nse_unresolved_audit.csv",index=False)
    pd.DataFrame(columns=["accession","cik","issuer","exchange","class","rule","filing_date","effectiveness","url","classification"]).to_csv(O/"form25_accessions.csv",index=False)
    pd.DataFrame(columns=["accession","cik","issuer","exchange","security_class","classification","evidence"]).to_csv(O/"form25_issuer_evidence.csv",index=False)
    pd.DataFrame(columns=["ticker","cik","company","accession","delisting_type","evidence"]).to_csv(O/"historical_common_stock_delisting_audit.csv",index=False)
    # manifest
    pre={"manifest_capture_mode":"PRE_RUN","git_commit_sha":"WORKTREE","data_sources":{"facts":{"path":str(F),"sha256":sha(F)},"amendments":{"path":str(S/"amendment_comparison_final.csv"),"sha256":sha(S/"amendment_comparison_final.csv")}},"command":"python -m tools.research.p10_5_6.finalize"}
    (O/"run_manifest_pre.json").write_text(json.dumps(pre,indent=2),encoding="utf-8")
    status={"generated_at":"2026-11-09T10:30:00+00:00","status":"P10_5_6_PARTIAL","amendment_rows":len(df),"normalized_equal":int((df.final_status=="NORMALIZED_EQUAL").sum()),"true_numeric_candidates":int((df.final_status=="TRUE_NUMERIC_CHANGE_CANDIDATE").sum()),"unit_incompatible":int((df.final_status=="UNIT_INCOMPATIBLE").sum()),"context_mismatch":int((df.final_status=="CONTEXT_MISMATCH").sum()),"duplicate":int((df.final_status=="DUPLICATE_FACT").sum()),"asof_tests":len(tests),"form25_rows":len(fm),"form25_unresolved":int((fm.final_classification=="UNRESOLVED").sum()),"ordinary_form25":0,"p10_6_allowed":False,"no_shadow":True}
    (O/"p10_5_6_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    post={"manifest_capture_mode":"PRE_RUN_PLUS_POST_RUN","pre_run":pre,"outputs":{p.name:{"path":str(p),"sha256":sha(p)} for p in O.glob("*.csv")},"status":"PARTIAL"}
    (O/"run_manifest.json").write_text(json.dumps(post,indent=2),encoding="utf-8")
    print(json.dumps(status,indent=2))


if __name__=="__main__":raise SystemExit(main())
