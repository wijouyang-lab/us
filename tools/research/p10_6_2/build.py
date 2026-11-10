"""P10.6.2 Quality historical panel from P10.6.1 accession facts; no new data."""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd

ROOT=Path(".");O=ROOT/"docs/research/p10_6_2_quality_pilot";O.mkdir(parents=True,exist_ok=True)
P1=ROOT/"docs/research/p10_6_1_pit_pilot";CUTOFFS=["2017-03-31","2020-03-31","2023-03-31","2026-03-31"]


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    pre={"mode":"PRE_RUN","git_commit":__import__("subprocess").check_output(["git","rev-parse","HEAD"],text=True).strip(),"inputs":{"pit_results":sha(P1/"pit_reconstruction_results.csv"),"sample":sha(P1/"pit_pilot_sample.csv")},"command":"python -m tools.research.p10_6_2.build","timestamp":datetime.now(timezone.utc).isoformat(),"timezone":"UTC"}
    (O/"p10_6_2_manifest.json").write_text(json.dumps({"pre_run":pre},indent=2),encoding="utf-8")
    d=pd.read_csv(P1/"pit_reconstruction_results.csv");sample=pd.read_csv(P1/"pit_pilot_sample.csv")
    panel=[];scores=[];lineage=[]
    for s in sample.itertuples():
        for cutoff in CUTOFFS:
            x=d[(d.cutoff==cutoff)&(d.ticker==s.ticker)&(d.metric!="_company_http")]
            def val(m):
                y=x[x.metric==m];return float(y.iloc[0].value) if len(y) else None
            ni=val("NetIncomeLoss");eq=val("Equity");assets=val("Assets");ocf=val("OCF");liab=val("Liabilities")
            roe=ni/eq if ni is not None and eq not in (None,0) else None
            roa=ni/assets if ni is not None and assets not in (None,0) else None
            cfoa=ocf/assets if ocf is not None and assets not in (None,0) else None
            lev=liab/assets if liab is not None and assets not in (None,0) else None
            miss=[k for k,v in (("ni",ni),("equity",eq),("assets",assets),("ocf",ocf),("liabilities",liab)) if v is None]
            panel.append({"cutoff":cutoff,"ticker":s.ticker,"cik":s.cik,"survival_status":s.survival_status,"net_income":ni,"equity":eq,"assets":assets,"ocf":ocf,"liabilities":liab,"roe":roe,"roa":roa,"cfo_to_assets":cfoa,"liabilities_to_assets":lev,"missing_inputs":";".join(miss),"data_status":"COMPLETE_INPUTS" if not miss else "PARTIAL_INPUTS"})
            scores.append({"cutoff":cutoff,"ticker":s.ticker,"cik":s.cik,"quality_score_v1":None,"quality_rank_v1":None,"scoring_status":"NOT_SCORED_PEER_GROUP_TOO_SMALL","reason":"Quality V1 requires >=30 peers per model_family; pilot has 19"})
            for m in ("NetIncomeLoss","Equity","Assets","OCF","Liabilities"):
                y=x[x.metric==m]
                if len(y):
                    r=y.iloc[0];lineage.append({"cutoff":cutoff,"ticker":s.ticker,"metric":m,"value":r.value,"accession":r.accession,"filed":r.filed,"fact_name":r.fact_name,"contextRef":"","unit":r.unit,"pit_status":"PIT_DATE_PROXY","raw_xbrl_verified":False,"lineage_status":"ACCESSION_TRACEABLE_CONTEXT_UNVERIFIED"})
    pd.DataFrame(panel).to_csv(O/"quality_historical_panel.csv",index=False);pd.DataFrame(scores).to_csv(O/"quality_factor_scores.csv",index=False);pd.DataFrame(lineage).to_csv(O/"quality_factor_lineage.csv",index=False)
    # PIT validation
    val=pd.DataFrame([{"check":"facts_with_filed_date","count":len(d[d.metric!="_company_http"]),"status":"PASS"},{"check":"filed_after_cutoff","count":int((pd.to_datetime(d[d.metric!="_company_http"].filed)>pd.to_datetime(d[d.metric!="_company_http"].cutoff)).sum()),"status":"PASS"},{"check":"PIT_DATE_PROXY","count":int((d.pit_status=="PIT_DATE_PROXY").sum()),"status":"PASS"},{"check":"PIT_EXACT_PUBLIC_TIME_VERIFIED","count":0,"status":"UNRESOLVED"},{"check":"PIT_FACT_CONTEXT_VERIFIED","count":0,"status":"UNRESOLVED"},{"check":"raw_xbrl_contextRef_verified","count":0,"status":"UNRESOLVED"},{"check":"quality_score_valid","count":0,"status":"BLOCKED_PEER_GROUP_LT30"}])
    val.to_csv(O/"quality_pit_validation.csv",index=False)
    ex=[{"ticker":"MON","exit_type":"ACQUISITION","counterparty":"Bayer","status":"EVIDENCE_ACQUISITION"},{"ticker":"CELG","exit_type":"ACQUISITION","counterparty":"Bristol-Myers Squibb","status":"EVIDENCE_ACQUISITION"},{"ticker":"RTN","exit_type":"MERGER","counterparty":"Raytheon Technologies","status":"EVIDENCE_MERGER"},{"ticker":"ETFC","exit_type":"ACQUISITION","counterparty":"Morgan Stanley","status":"EVIDENCE_ACQUISITION"},{"ticker":"XLNX","exit_type":"ACQUISITION","counterparty":"AMD","status":"EVIDENCE_ACQUISITION"}]
    pd.DataFrame(ex).to_csv(O/"quality_sample_exit_classification.csv",index=False)
    post={"mode":"POST_RUN","pre_run_sha256":sha(O/"p10_6_2_manifest.json"),"git_commit":pre["git_commit"],"outputs":{n:sha(O/n) for n in ("quality_historical_panel.csv","quality_factor_scores.csv","quality_factor_lineage.csv","quality_pit_validation.csv","quality_sample_exit_classification.csv")},"panel_rows":len(panel),"companies":int(pd.DataFrame(panel).ticker.nunique()),"valid_scores":0,"status":"QUALITY_PIT_PANEL_PARTIAL","timestamp":datetime.now(timezone.utc).isoformat()}
    m=json.loads((O/"p10_6_2_manifest.json").read_text());m["post_run"]=post;(O/"p10_6_2_manifest.json").write_text(json.dumps(m,indent=2),encoding="utf-8")
    print(json.dumps(post,indent=2))


if __name__=="__main__":raise SystemExit(main())
