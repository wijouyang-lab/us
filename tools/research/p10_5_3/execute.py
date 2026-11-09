"""P10.5.3 actual SEC download execution and AAPL fact consolidation."""
from __future__ import annotations
import csv,hashlib,json,zipfile
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd,requests

O=Path("data/research/p10_5_3_execution_recovery");C=O/"cache"


def main():
    log=json.load(open(O/"download_log.json"));rows=[];dfields={}
    for x in log:
        z=zipfile.ZipFile(C/f"{x['quarter']}.zip")
        def rd(n):
            with z.open(n) as f:return pd.read_csv(f,sep="\t",dtype=str,encoding="latin1",low_memory=False,nrows=None)
        sub=rd("sub.txt");num=rd("num.txt");tag=rd("tag.txt");pre=rd("pre.txt")
        for d in (sub,num,tag,pre):d.columns=[c.lower() for c in d.columns]
        x.update({"sub_rows":len(sub),"num_rows":len(num),"tag_rows":len(tag),"pre_rows":len(pre),"num_columns":list(num.columns),"status":"PARSED"})
        rows.append(x);dfields[x["quarter"]]=list(num.columns)
    pd.DataFrame(rows).to_csv(O/"aapl_quarterly_dataset_manifest.csv",index=False)
    pd.DataFrame([{"quarter":q,"columns":",".join(c)} for q,c in dfields.items()]).to_csv(O/"sec_num_schema_diff.csv",index=False)
    # AAPL facts from prior real accession parses
    f1=pd.read_csv("data/research/p10_3_sec_xbrl_coverage/separate_xbrl_facts.csv",dtype={"accession":str})
    f2=pd.read_csv("data/research/p10_2_sec_as_filed/aapl_as_filed_facts.csv",dtype={"accession":str})
    facts=pd.concat([f1,f2],ignore_index=True);facts.to_csv(O/"aapl_historical_financial_facts.csv",index=False)
    cov=[]
    for f in facts.field.unique():
        sub=facts[facts.field==f];cov.append({"field":f,"facts":len(sub),"accessions":sub.accession.nunique(),"first_period":sub.period_start.min(),"last_period":sub.period_end.max()})
    pd.DataFrame(cov).to_csv(O/"aapl_financial_field_coverage.csv",index=False)
    # amendment check: matching field+period, compare values
    line=[]
    for acc in facts.accession.unique():
        if not (acc.endswith("A") or acc in []):continue
        # accession endings do not identify form; use status index
    idx=pd.read_csv("data/research/p10_3_sec_xbrl_coverage/aapl_all_status.csv",dtype={"accession":str})
    am=idx[idx.form.isin(["10-K/A","10-Q/A"])]
    for r in am.itertuples():
        base=idx[(idx.form==r.form.replace("/A",""))&(idx.filing_date<r.filing_date)].sort_values("filing_date").tail(1)
        if base.empty:continue
        b=base.iloc[0];fa=facts[facts.accession==r.accession];fb=facts[facts.accession==b.accession]
        for x in fa.itertuples():
            y=fb[(fb.field==x.field)&(fb.period_start==x.period_start)&(fb.period_end==x.period_end)]
            if len(y):
                line.append({"original_accession":b.accession,"amendment_accession":r.accession,"form":r.form,"field":x.field,"period_start":x.period_start,"period_end":x.period_end,"original_value":y.iloc[0].value,"amendment_value":x.value,"classification":"TEXT_ONLY_AMENDMENT" if abs(float(y.iloc[0].value)-float(x.value))<1e-9 else "NUMERIC_RESTATEMENT"})
    pd.DataFrame(line).to_csv(O/"restatement_lineage.csv",index=False)
    pd.DataFrame(line).to_csv(O/"fact_version_history.csv",index=False)
    # real as-of tests only where numeric change exists
    tests=[]
    for x in line:
        if x["classification"]=="NUMERIC_RESTATEMENT":
            tests.append({"accession":x["amendment_accession"],"field":x["field"],"before":x["original_value"],"after":x["amendment_value"],"test":"PENDING_REAL_TIMESTAMP"})
    pd.DataFrame(tests).to_csv(O/"real_asof_query_tests.csv",index=False)
    # EDGAR full-text search attempt (actual request, may fail)
    search={"attempted":True,"url":"https://efts.sec.gov/LATEST/search-index?q=%22FORM%2025-NSE%22","status":"","error":""}
    try:
        r=requests.get(search["url"],headers={"User-Agent":"us-pit-research/1.0 research@example.com"},timeout=30);search["status"]=r.status_code;search["bytes"]=len(r.content);search["preview"]=r.text[:300]
    except Exception as e:search["error"]=str(e)[:300]
    json.dump(search,open(O/"edgar_search_log.json","w"),indent=2)
    pd.DataFrame(columns=["accession","filed_by_cik","subject_cik","subject_name","form","filing_date","effectiveness_date","security_class","status"]).to_csv(O/"edgar_form25_search_results.csv",index=False)
    pd.DataFrame(columns=["ticker","cik","company","exchange","accession","filing_date","effectiveness","security","delisting_type","evidence_url","confidence"]).to_csv(O/"delisting_evidence.csv",index=False)
    # 10-company validation sample from P10.5 (not promoted to historical)
    acc=pd.read_csv("data/research/p10_5_sec_multi_period/cross_section_30_accession_coverage.csv")
    sample=acc[acc.ticker.isin(sorted(acc.ticker.unique())[:10])].copy();sample["sample_role"]="P10_5_3_VALIDATION_ONLY";sample.to_csv(O/"valid_sample_10_accessions.csv",index=False)
    # summary status
    numschema={q:set(v) for q,v in dfields.items()};seg={q:("segments" in v) for q,v in numschema.items()}
    status={"generated_at":datetime.now(timezone.utc).isoformat(),"status":"P10_5_3_PARTIAL","datasets_downloaded":len(rows),"dataset_quarters":[x["quarter"] for x in rows],"aapl_facts":len(facts),"aapl_amendments":len(am),"amendment_rows":len(line),"real_numeric_restatements":sum(1 for x in line if x["classification"]=="NUMERIC_RESTATEMENT"),"edgar_search":search,"valid_sample_companies":10,"delisted_companies":0,"qtd_ytd":False,"p10_6_allowed":False,"data_blocked":["real delisted sample","numeric restatement case","real QTD/YTD derivation"],"no_shadow":True}
    (O/"p10_5_3_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    (O/"aapl_fact_source_audit.json").write_text(json.dumps({"source":"P10.3 separate + P10.2 inline facts","no_companyfacts_backfill":True,"facts":len(facts)},indent=2),encoding="utf-8")
    print(json.dumps({"datasets":status["dataset_quarters"],"schema":seg,"aapl_facts":len(facts),"amendment_rows":len(line),"numeric_restatements":status["real_numeric_restatements"],"search":search},indent=2))


if __name__=="__main__":raise SystemExit(main())
