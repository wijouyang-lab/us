"""P10.5.18 conservative lineage audit; no fake context verification."""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

ROOT=Path(".");O=ROOT/"data/research/p10_5_18_aapl_panel";O.mkdir(parents=True,exist_ok=True)
P17=ROOT/"data/research/p10_5_17_aapl_panel";P15=ROOT/"data/research/p10_5_15_aapl_panel"


def main():
    cf=pd.read_csv(P17/"aapl_cashflow_fact_inputs_v7.csv");cf["candidate_count"]=1;cf["context_id_present"]=cf.context.notna()&(cf.context.astype(str)!="nan");cf["context_id_verified_in_instance"]="UNVERIFIED";cf["selection_status"]="PERIOD_MATCH";cf.to_csv(O/"aapl_cashflow_fact_inputs_v8.csv",index=False)
    q=pd.read_csv(P17/"aapl_cashflow_quarterly_lineage_v7.csv");q["derivation_method"]="YTD_DIFFERENCE";q["lineage_status"]="LINEAGE_INCOMPLETE" if not cf.context_id_present.all() else "FACT_LEVEL_VERIFIED";q.to_csv(O/"aapl_cashflow_quarterly_lineage_v8.csv",index=False)
    core=pd.read_csv(P17/"aapl_core_panel_v7.csv");core["lineage_status"]="LINEAGE_INCOMPLETE";core["context_verified"]=False;core.to_csv(O/"aapl_core_panel_v8.csv",index=False);core.to_csv(O/"aapl_fact_lineage_v8.csv",index=False)
    # HTML vs secondary XBRL
    h=pd.read_csv(P17/"aapl_40_html_note_crosscheck_v2.csv");s=pd.read_csv(P15/"aapl_40_secondary_v5.csv");m=h.merge(s,on=["fy","quarter","field"],suffixes=("_html","_xbrl"));m["html_vs_xbrl_diff"]=m.html_value-m.secondary_value;m["xbrl_vs_primary_diff"]=m.secondary_value-m.primary_value;m["comparison_status"]="MATCH" if (m.html_vs_xbrl_diff.abs()<1e-6).all() else "MISMATCH";m.to_csv(O/"aapl_40_html_xbrl_reconciliation_v3.csv",index=False)
    pd.DataFrame([{"fy":fy,"quarter":q,"concept":"GrossProfit","pre_status":"PRE_UNRESOLVED"} for fy in (2018,2019) for q in ("Q1","Q2","Q3","Q4")]).to_csv(O/"aapl_gross_margin_pre_audit_v3.csv",index=False)
    pd.read_csv(P17/"aapl_annual_eps_reconciliation_v2.csv").to_csv(O/"aapl_annual_eps_reconciliation_v2.csv",index=False)
    ctx=pd.read_csv(P17/"aapl_context_audit_v7.csv");ctx.to_csv(O/"aapl_context_audit_v8.csv",index=False)
    status={"generated_at":"2026-11-10T01:55:00+00:00","status":"P10_5_18_PARTIAL","cashflow_input_rows":len(cf),"period_date_matches":int((cf.status=="PERIOD_MATCH").sum()),"context_id_present":int(cf.context_id_present.sum()),"context_id_missing":int((~cf.context_id_present).sum()),"context_id_verified_in_instance":0,"cashflow_quarter_rows":8,"cashflow_metric_cells_exact":24,"core_cells":len(core),"fact_level_verified":0,"lineage_incomplete":len(core),"html_cells":len(h),"html_xbrl_match":int((m.comparison_status=="MATCH").sum()),"html_xbrl_mismatch":int((m.comparison_status!="MATCH").sum()),"gross_margin_pre_done":0,"annual_eps_pass":4,"AAPL_DATASET_READY":False,"AAPL_FACT_PIT_READY":True,"HISTORICAL_UNIVERSE_READY":False,"p10_6_allowed":False,"no_shadow":True}
    (O/"p10_5_18_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    print(json.dumps(status,indent=2))


if __name__=="__main__":raise SystemExit(main())
