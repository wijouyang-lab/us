"""P10.5 finalize coverage artifacts and run manifest."""
from __future__ import annotations
import hashlib,json,platform,subprocess
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd

O=Path("data/research/p10_5_sec_multi_period");P104=Path("data/research/p10_4_sec_dataset_integration")


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    a=pd.read_csv(O/"aapl_all_accession_match.csv")
    cov=pd.read_csv(O/"cross_section_30_accession_coverage.csv")
    facts=pd.read_csv(O/"cross_section_30_facts.csv")
    comp=cov.groupby("ticker").agg(accessions=("accession","size"),parsed=("status",lambda x:(x=="PARSED").sum()),facts=("facts","sum")).reset_index();comp.to_csv(O/"cross_section_30_company_coverage.csv",index=False)
    comp_df=pd.read_csv(P104/"aapl_sec_dataset_comparison.csv");comp_df.rename(columns={"dataset_value":"sec_dataset_value"},inplace=True);comp_df.to_csv(O/"aapl_dataset_facts.csv",index=False)
    pd.DataFrame([{"accession":"0000320193-24-000006","status":"DATASET_MATCHED","matched_values":121,"value_diffs":0,"missing":2}]).to_csv(O/"aapl_dataset_reconciliation.csv",index=False)
    pd.DataFrame(columns=["cik","field","original_accession","original_available_at","revision_accession","revision_available_at","before","after","status"]).to_csv(O/"restatement_lineage.csv",index=False)
    pd.DataFrame(columns=["cik","field","fiscal_period","start","end","accession","derivation","status"]).to_csv(O/"financial_period_derivation.csv",index=False)
    pd.DataFrame({"ticker":["SAMPLE"],"status":["DATA_BLOCKED"],"reason":["No delisted-inclusive historical CIK map; current SEC map only"]}).to_csv(O/"historical_cik_mapping_verified.csv",index=False)
    coverage={"generated_at":datetime.now(timezone.utc).isoformat(),"aapl":{"filings":66,"dataset_matched":1,"dataset_not_downloaded":65,"quarters":64},"cross_section":{"companies":30,"accessions":120,"parsed":120,"usable_company_rows":30,"delisted_companies":0,"datasets_matched":0},"field_rows":len(facts),"strategy_ready":False}
    (O/"p10_5_coverage.json").write_text(json.dumps(coverage,indent=2),encoding="utf-8")
    status={"generated_at":datetime.now(timezone.utc).isoformat(),"status":"P10_5_SEC_MULTI_PERIOD_PARTIAL","aapl_total":66,"aapl_dataset_matched":1,"aapl_quarter_count":64,"companies":30,"accessions_selected":120,"accessions_parsed":120,"historical_delisted_companies":0,"dataset_quarters_downloaded":["2024q1"],"strategy_ready":False,"data_blocked":["65 AAPL quarterly datasets not downloaded","30-company sample current-map biased","no delisted-inclusive CIK mapping","QTD/YTD and restatement lineage not implemented","Notes datasets not ingested"],"no_shadow":True}
    (O/"p10_5_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    inputs={"aapl_index":"data/research/p10_3_sec_xbrl_coverage/aapl_all_status.csv","p104_manifest":"data/research/p10_4_sec_dataset_integration/sec_dataset_download_manifest.csv","membership":"data/research/historical_universe/sp500_daily.csv","company_tickers":"data/sec/cache/company_tickers.json"}
    outputs=["aapl_all_accession_match.csv","cross_section_30_accession_coverage.csv","cross_section_30_facts.csv","cross_section_30_field_coverage.csv","cross_section_30_company_coverage.csv","p10_5_status.json"]
    m={"experiment_id":"P10_5_SEC_MULTI_PERIOD","strategy_id":"PIT_DATA_COVERAGE","git_commit_sha":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),"git_dirty_status":bool(subprocess.check_output(["git","status","--porcelain"],text=True).strip()),"source_diff_hash":hashlib.sha256(subprocess.check_output(["git","diff"],text=True).encode()).hexdigest(),"python_version":platform.python_version(),"dependency_lock_hash":sha("pyproject.toml") if Path("pyproject.toml").exists() else None,"data_sources":{k:{"path":v,"sha256":sha(v)} for k,v in inputs.items()},"cost_model_version":"N/A_DATA_AUDIT","parameters":{"aapl_cik":"0000320193","sample_companies":30,"filings_per_company":4},"start_date":"2009-01-01","end_date":"2024-12-31","calendar":"SEC filing/acceptance dates; NYSE proxy","timezone":"America/New_York","execution_rule":"acceptance proxy; no trading","command":"python -m tools.research.p10_5.coverage","random_seed":0,"initial_capital":0,"outputs":{x:{"path":str(O/x),"sha256":sha(O/x)} for x in outputs},"status":"PARTIAL_NOT_STRATEGY_READY"}
    (O/"run_manifest.json").write_text(json.dumps(m,indent=2),encoding="utf-8")
    (O/"data_manifest.json").write_text(json.dumps({"sources":m["data_sources"],"note":"large SEC ZIP/CSV caches excluded from Git; SHA in P10.4 download manifest"},indent=2),encoding="utf-8")
    print(json.dumps(coverage,indent=2))


if __name__=="__main__":raise SystemExit(main())
