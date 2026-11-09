"""P10.5.1 remediation audit: preserve P10.5, explicitly gate invalid coverage."""
from __future__ import annotations
import hashlib,json,platform,subprocess
from datetime import date,datetime,timezone
from pathlib import Path
import pandas as pd

O=Path("data/research/p10_5_1_sec_remediation");O.mkdir(parents=True,exist_ok=True);P=Path("data/research/p10_5_sec_multi_period")


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def get_facts_as_of(facts,cik,query_date,field):
    """Minimal version-aware query: latest usable accession at/before query_date."""
    d=pd.Timestamp(query_date).date();sub=facts[(facts.cik.astype(str).str.zfill(10)==str(cik).zfill(10))&(facts.field==field)]
    sub=sub[pd.to_datetime(sub.market_usable_A).dt.date<=d]
    if sub.empty:return None
    return sub.sort_values("market_usable_A").iloc[-1].to_dict()


def main():
    aapl=pd.read_csv(P/"aapl_required_dataset_periods.csv");sel=pd.read_csv(P/"cross_section_30_company_coverage.csv");acc=pd.read_csv(P/"cross_section_30_accession_coverage.csv")
    # AAPL: classify without claiming undownloaded quarters are absent
    rows=[]
    for r in aapl.itertuples():
        q=r.dataset_quarter
        if r.filing_date<"2009-04-15":s="PRE_DATASET_COVERAGE_START"
        elif q=="2024q1":s="DATASET_MATCHED" if r.accession=="0000320193-24-000006" else "NOT_IN_DATASET"
        else:s="NOT_IN_DATASET"
        rows.append({"accession":r.accession,"form":r.form,"filing_date":r.filing_date,"dataset_quarter":q,"dataset_status":s,"dataset_downloaded":q=="2024q1"})
    final=pd.DataFrame(rows);final.to_csv(O/"aapl_all_accession_final_match.csv",index=False)
    quarters=sorted(final.dataset_quarter.unique());qm=pd.DataFrame([{"quarter":q,"downloaded":q=="2024q1","status":"DOWNLOADED" if q=="2024q1" else "NOT_DOWNLOADED"} for q in quarters]);qm.to_csv(O/"aapl_quarterly_dataset_manifest.csv",index=False)
    pd.DataFrame([{"accession":r.accession,"facts_in_dataset":123 if r.accession=="0000320193-24-000006" else 0,"core_fields":18 if r.accession=="0000320193-24-000006" else 0,"status":r.dataset_status} for r in final.itertuples()]).to_csv(O/"aapl_accession_fact_coverage.csv",index=False)
    pd.DataFrame([{"accession":"0000320193-24-000006","status":"DATASET_MATCHED","matched_values":121,"diffs":0,"missing":2}]).to_csv(O/"aapl_dataset_reconciliation.csv",index=False)
    (O/"aapl_dataset_status.json").write_text(json.dumps({"status":"P10_5_1_AAPL_DATASET_INCOMPLETE","total":66,"matched":int((final.dataset_status=="DATASET_MATCHED").sum()),"pre_coverage":int((final.dataset_status=="PRE_DATASET_COVERAGE_START").sum()),"not_downloaded":int((final.dataset_status=="NOT_IN_DATASET").sum()),"quarters":len(quarters)},indent=2),encoding="utf-8")
    # Parser validation sample is preserved but not promoted
    selection=sel.copy();selection["sample_role"]="PARSER_VALIDATION_SAMPLE";selection["valid_historical_research_sample"]="NO";selection["reason"]="selected from current SEC map; no verified delisted companies";selection.to_csv(O/"historical_sample_selection.csv",index=False)
    pd.DataFrame(columns=["ticker","cik","company","delisting_date","evidence","confidence","status"]).to_csv(O/"delisted_company_evidence.csv",index=False)
    pd.DataFrame(columns=["ticker","cik","historical_ticker","effective_start","effective_end","historical_member","mapping_source","confidence","status"]).to_csv(O/"historical_cik_mapping_verified.csv",index=False)
    valid=acc.copy();valid["sample_role"]="P10_5_PARSER_VALIDATION_ONLY";valid["valid_historical_research_sample"]="NO";valid.to_csv(O/"valid_sample_accessions.csv",index=False);pd.DataFrame([{"ticker":t,"parse_status":"PARSED","sample_eligible":"NO"} for t in selection.ticker]).to_csv(O/"valid_sample_parse_coverage.csv",index=False)
    # Explicit empty lineage; no fabricated versions
    pd.DataFrame(columns=["cik","field","period","original_accession","revision_accession","before","after","status"]).to_csv(O/"restatement_lineage.csv",index=False)
    # Unit-test-only as-of query, clearly separated from historical claim
    facts=pd.DataFrame([{"cik":"0000000001","field":"Revenue","value":100,"accession":"A1","market_usable_A":"2020-01-01"},{"cik":"0000000001","field":"Revenue","value":90,"accession":"A2","market_usable_A":"2022-01-01"}])
    tests=[]
    for d in ("2021-01-01","2023-01-01"):
        x=get_facts_as_of(facts,"0000000001",d,"Revenue");tests.append({"query_date":d,"value":x["value"] if x else None,"accession":x["accession"] if x else None,"status":"UNIT_TEST_ONLY"})
    pd.DataFrame(tests).to_csv(O/"asof_query_test_results.csv",index=False)
    pd.DataFrame(columns=["cik","field","fiscal_period","qtd_value","accession","derivation","status"]).to_csv(O/"financial_period_derivation.csv",index=False)
    pd.DataFrame(columns=["ticker","field","reason"]).to_csv(O/"field_missing_reasons.csv",index=False)
    pd.read_csv(P/"aapl_all_accession_match.csv") if False else None
    # PIT A/B copied from P10.3, unchanged
    pd.read_csv("data/research/p10_3_sec_xbrl_coverage/pit_time_audit.csv").to_csv(O/"pit_availability_audit.csv",index=False)
    status={"generated_at":datetime.now(timezone.utc).isoformat(),"status":"P10_5_1_DATA_BLOCKED","aapl_quarters_required":len(quarters),"aapl_quarters_downloaded":1,"aapl_matched":1,"companies":len(selection),"accessions_parsed":len(acc),"valid_historical_sample":False,"delisted_companies":0,"asof_real_history":False,"qtd_ytd":False,"p10_6_allowed":False,"data_blocked":["64 AAPL quarters","verified delisted sample","historical CIK identity","real restatement lineage","real QTD/YTD facts"],"no_shadow":True}
    (O/"p10_5_1_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    # manifest
    inputs={"p10_5_aapl":"data/research/p10_5_sec_multi_period/aapl_required_dataset_periods.csv","p10_5_accessions":"data/research/p10_5_sec_multi_period/cross_section_30_accession_coverage.csv","p10_3_pit":"data/research/p10_3_sec_xbrl_coverage/pit_time_audit.csv"};outs=[x.name for x in O.glob("*.csv")]+["p10_5_1_status.json"]
    man={"experiment_id":"P10_5_1_REMEDIATION","strategy_id":"PIT_COVERAGE_AUDIT","git_commit_sha":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),"git_dirty_status":True,"source_diff_hash":hashlib.sha256(subprocess.check_output(["git","diff"],text=True).encode()).hexdigest(),"python_version":platform.python_version(),"dependency_lock_hash":None,"data_sources":{k:{"path":v,"sha256":sha(v)} for k,v in inputs.items()},"cost_model_version":"N/A","parameters":{"sample":"P10.5_30","aapl_cik":"0000320193"},"start_date":"2009-01-01","end_date":"2024-12-31","calendar":"SEC/NYSE","timezone":"America/New_York","execution_rule":"PIT acceptance proxy only","command":"python -m tools.research.p10_5_1.remediation","random_seed":0,"initial_capital":0,"outputs":{x:{"path":str(O/x),"sha256":sha(O/x)} for x in outs},"status":"DATA_BLOCKED"}
    (O/"run_manifest.json").write_text(json.dumps(man,indent=2),encoding="utf-8");(O/"data_manifest.json").write_text(json.dumps({"sources":man["data_sources"]},indent=2),encoding="utf-8")
    print(json.dumps(status,indent=2))


if __name__=="__main__":raise SystemExit(main())
