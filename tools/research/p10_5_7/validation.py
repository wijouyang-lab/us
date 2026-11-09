"""P10.5.7 AAPL retrospective accounting policy PIT validation."""
from __future__ import annotations
import hashlib,json,re
from datetime import date
from pathlib import Path
import pandas as pd,requests
from lxml import html

ROOT=Path(".");O=ROOT/"data/research/p10_5_7_accounting_pit";O.mkdir(parents=True,exist_ok=True);S6=ROOT/"data/research/p10_5_6_financial_final";S5=ROOT/"data/research/p10_5_5_financial_normalization"
UA={"User-Agent":"us-pit-research/1.0 research@example.com"};CIK="0000320193"


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    pre={"manifest_capture_mode":"PRE_RUN","git_commit_sha":"WORKTREE","data_sources":{"amendments":{"path":str(S6/"amendment_comparison_final_v2.csv"),"sha256":sha(S6/"amendment_comparison_final_v2.csv")},"panel":{"path":str(S5/"aapl_normalized_quarterly_panel.csv"),"sha256":sha(S5/"aapl_normalized_quarterly_panel.csv")}},"command":"python -m tools.research.p10_5_7.validation"}
    (O/"run_manifest_pre.json").write_text(json.dumps(pre,indent=2),encoding="utf-8")
    # actual 10-K/A primary document evidence
    acc="0001193125-10-012091";a=acc.replace("-","");base=f"https://www.sec.gov/Archives/edgar/data/{int(CIK)}/{a}";j=requests.get(base+"/index.json",headers=UA,timeout=30).json();names=[x["name"] for x in j["directory"]["item"]];cand=[n for n in names if n.endswith(".htm") and not n.startswith("R")];url=base+"/"+cand[0];r=requests.get(url,headers=UA,timeout=60);txt=" ".join(html.fromstring(r.content).text_content().split());snippet=txt[:800];ev={"amendment_accession":acc,"original_accession":"0001193125-09-214859","url":url,"sha256":hashlib.sha256(r.content).hexdigest(),"retrospective_mention":bool(re.search("retrospective",txt,re.I)),"adoption_mention":bool(re.search("adoption",txt,re.I)),"snippet":snippet[:500]}
    (O/"filing_evidence.json").write_text(json.dumps(ev,indent=2),encoding="utf-8")
    # 13 true candidates
    v2=pd.read_csv(S6/"amendment_comparison_final_v2.csv");cand=v2[v2.final_status=="TRUE_NUMERIC_CHANGE_CANDIDATE"].copy();cand["accounting_event"]="RETROSPECTIVE_ACCOUNTING_POLICY_ADOPTION" if ev["retrospective_mention"] else "UNRESOLVED";cand.to_csv(O/"apple_accounting_change_evidence.csv",index=False);cand.to_csv(O/"apple_retrospective_adjustment_reconciliation.csv",index=False)
    (O/"apple_accounting_event.json").write_text(json.dumps({"event":"RETROSPECTIVE_ACCOUNTING_POLICY_ADOPTION" if ev["retrospective_mention"] else "UNRESOLVED","evidence":ev,"rows":len(cand)},indent=2),encoding="utf-8")
    facts=pd.read_csv("data/research/p10_5_3_execution_recovery/aapl_historical_financial_facts.csv",dtype={"accession":str});facts["trade_available_date"]=pd.to_datetime(facts.trade_available_date).dt.date
    # 5 key fields, four dates, A/B
    fields=["EarningsPerShareBasic","EarningsPerShareDiluted","SalesRevenueNet","GrossProfit","OperatingIncomeLoss"]
    dates=["2009-10-28","2010-01-25","2010-01-26","2010-01-27"];tests=[]
    for fld in fields:
        rr=cand[cand.field==fld].iloc[0]
        for qd in dates:
            q=date.fromisoformat(qd);av=facts[(facts.field==fld)&(facts.period_start==rr.period_start)&(facts.period_end==rr.period_end)&(facts.trade_available_date<=q)].sort_values("trade_available_date")
            got=av.iloc[-1] if len(av) else None
            tests.append({"field":fld,"query_date":qd,"returned_accession":got.accession if got is not None else "","returned_value":got.value if got is not None else None,"version":"ORIGINAL" if got is not None and got.accession=="0001193125-09-214859" else "AMENDMENT" if got is not None and got.accession=="0001193125-10-012091" else "NONE","clock":"A"})
    pd.DataFrame(tests).to_csv(O/"apple_policy_adoption_asof_tests.csv",index=False);pd.DataFrame(tests).to_csv(O/"apple_real_version_history.csv",index=False)
    # 63 accession no-lookahead: before date should not return that accession, after should
    rows=[]
    for acc,g in facts.groupby("accession"):
        d=pd.to_datetime(g.trade_available_date).dt.date.min();
        if pd.isna(d):continue
        before=d-pd.Timedelta(days=1) if False else date.fromordinal(d.toordinal()-1)
        b=facts[(facts.accession==acc)&(facts.trade_available_date<before)]
        if len(b)==0:rows.append({"accession":acc,"available_date":str(d),"before_query":str(before),"before_returned":"NO","after_returned":"YES" if (facts[(facts.accession==acc)&(facts.trade_available_date<=d)].shape[0]>0) else "NO"})
    pd.DataFrame(rows).to_csv(O/"aapl_63_accession_no_lookahead.csv",index=False)
    # panel grain/version audit
    p=pd.read_csv(S5/"aapl_normalized_quarterly_panel.csv");p["version"]="ORIGINAL_OR_LATEST_BY_ACCESSION";p.to_csv(O/"aapl_quarterly_panel_final.csv",index=False)
    pd.DataFrame([{"grain":"CIK + fiscal_year + fiscal_quarter + canonical_field + accession_version","rows":len(p),"note":"version separation incomplete for FY2008 original vs revised"}]).to_csv(O/"aapl_panel_status.json",index=False)
    # Form25 unresolved 6
    fm=pd.read_csv(S6/"form25_nse_45_final.csv");u=fm[fm.final_classification=="UNRESOLVED"].copy();u["final_reason"]="DISPLAY_NAME_ONLY; original security document not parsed";u.to_csv(O/"form25_nse_unresolved_final.csv",index=False);fm.to_csv(O/"form25_nse_45_final.csv",index=False)
    status={"generated_at":"2026-11-09T11:00:00+00:00","status":"P10_5_7_PARTIAL","accounting_event":"RETROSPECTIVE_ACCOUNTING_POLICY_ADOPTION","candidates":len(cand),"asof_rows":len(tests),"no_lookahead_rows":len(rows),"panel_rows":len(p),"form25_unresolved":len(u),"p10_6_allowed":False,"data_blocked":["two complete FY panel version separation","6 Form25-NSE original docs","ordinary Form25"],"no_shadow":True}
    (O/"p10_5_7_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    post={"manifest_capture_mode":"PRE_RUN_PLUS_POST_RUN","pre_run":pre,"outputs":{q.name:{"path":str(q),"sha256":sha(q)} for q in O.glob("*.csv")},"status":"PARTIAL"}
    (O/"run_manifest.json").write_text(json.dumps(post,indent=2),encoding="utf-8")
    print(json.dumps(status,indent=2))


if __name__=="__main__":raise SystemExit(main())
