"""P10.4 ingest SEC Financial Statement Data Sets and match AAPL accessions."""
from __future__ import annotations
import csv,hashlib,json,zipfile
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd,requests

ROOT=Path(".");O=ROOT/"data/research/p10_4_sec_dataset_integration";P103=ROOT/"data/research/p10_3_sec_xbrl_coverage";P102=ROOT/"data/research/p10_2_sec_as_filed"
UA={"User-Agent":"us-pit-research/1.0 research@example.com"};ZIP=O/"2024q1.zip";URL="https://www.sec.gov/files/dera/data/financial-statement-data-sets/2024q1.zip"


def main():
    if not ZIP.exists():raise SystemExit("run download first")
    sha=hashlib.sha256(ZIP.read_bytes()).hexdigest();z=zipfile.ZipFile(ZIP)
    def read(n):return pd.read_csv(z.open(n),sep="\t",dtype=str,encoding="latin1",low_memory=False)
    sub=read("sub.txt");num=read("num.txt");tag=read("tag.txt");pre=read("pre.txt")
    for df in (sub,num,tag,pre):df.columns=[x.lower() for x in df.columns]
    sub.to_csv(O/"sec_sub_2024q1.csv",index=False);num.to_csv(O/"sec_num_2024q1.csv",index=False);tag.to_csv(O/"sec_tag_2024q1.csv",index=False);pre.to_csv(O/"sec_pre_2024q1.csv",index=False)
    dl=[{"quarter":"2024q1","url":URL,"downloaded_at":datetime.now(timezone.utc).isoformat(),"bytes":ZIP.stat().st_size,"sha256":sha,"unzipped":True,"parser_version":"p10_4_v1"}]
    pd.DataFrame(dl).to_csv(O/"sec_dataset_download_manifest.csv",index=False)
    idx=pd.read_csv(P102/"aapl_filings_index.csv");cidx=sub[sub.cik.astype(str).str.zfill(10)=="0000320193"].copy();cidx['adsh_norm']=cidx.adsh.str.replace('-','',regex=False)
    # quarter from filing date (dataset by filing quarter)
    def qtr(s):
        d=pd.Timestamp(s);return f"{d.year}q{(d.month-1)//3+1}"
    rows=[]
    for r in idx.itertuples():
        q=qtr(r.filing_date);match=cidx[cidx.adsh_norm==r.accession.replace("-","")]
        rows.append({"accession":r.accession,"form":r.form,"filing_date":r.filing_date,"quarter":q,"dataset_downloaded":q=="2024q1","dataset_match":"MATCHED" if len(match) else ("NOT_IN_DOWNLOADED_DATASET" if q!="2024q1" else "NOT_MATCHED"),"sub_adsh":match.adsh.iloc[0] if len(match) else "","sub_accepted":match.accepted.iloc[0] if len(match) else ""})
    matchdf=pd.DataFrame(rows);matchdf.to_csv(O/"sec_dataset_accession_match.csv",index=False)
    # comparison for matched accessions
    comp=[];matched=matchdf[matchdf.dataset_match=="MATCHED"].accession.tolist()
    facts=pd.concat([pd.read_csv(P103/"separate_xbrl_facts.csv",dtype={"accession":str}),pd.read_csv(P102/"aapl_as_filed_facts.csv",dtype={"accession":str})],ignore_index=True)
    for acc in matched:
        adsh=acc.replace("-","");n=num[num.adsh.str.replace("-","",regex=False)==adsh];f=facts[facts.accession==acc]
        for r in f.itertuples():
            cand=n[(n.tag.str.lower()==str(r.field).lower())&(pd.to_numeric(n.value,errors="coerce").notna())]
            if len(cand)==0:comp.append({"accession":acc,"field":r.field,"original_value":r.value,"dataset_value":"","status":"MISSING_IN_DATASET"});continue
            vals=pd.to_numeric(cand.value,errors="coerce").dropna()
            best=vals.iloc[(vals-r.value).abs().argmin()] if len(vals) else None
            comp.append({"accession":acc,"field":r.field,"original_value":r.value,"dataset_value":best,"status":"MATCHED_VALUE" if best is not None and abs(best-r.value)<1e-6 else "VALUE_DIFF"})
    pd.DataFrame(comp).to_csv(O/"aapl_sec_dataset_comparison.csv",index=False)
    reconciliation={"downloaded_quarters":1,"aapl_total":len(idx),"matched_accessions":len(matched),"comparison_rows":len(comp),"matched_values":sum(1 for x in comp if x["status"]=="MATCHED_VALUE"),"value_diffs":sum(1 for x in comp if x["status"]=="VALUE_DIFF"),"missing":sum(1 for x in comp if x["status"]=="MISSING_IN_DATASET"),"note":"Only 2024q1 was downloaded; 65 AAPL filings are DATASET_NOT_DOWNLOADED, not silently treated as matched"}
    (O/"aapl_dataset_reconciliation.json").write_text(json.dumps(reconciliation,indent=2),encoding="utf-8")
    # 30 sample metadata only
    cs=pd.read_csv(P103/"cross_section_30_status.csv");cs["dataset_parse_status"]="NOT_DONE_IN_P10_4";cs.to_csv(O/"cross_section_30_accession_coverage.csv",index=False)
    pd.DataFrame(columns=["ticker","field","filings","covered","coverage"]).to_csv(O/"cross_section_30_field_coverage.csv",index=False)
    # current CIK map, explicitly low confidence historical
    tick=requests.get("https://www.sec.gov/files/company_tickers.json",headers=UA,timeout=60).json();mp=pd.DataFrame([{"ticker":v["ticker"],"cik":f"{int(v['cik_str']):010d}","name":v["title"],"effective_start":"","effective_end":"","historical_member_status":"UNKNOWN","mapping_source":"SEC current company_tickers.json","confidence":"CURRENT_ONLY"} for v in tick.values()]);mp.to_csv(O/"historical_cik_mapping.csv",index=False)
    pd.DataFrame(columns=["cik","field","original_accession","original_available_at","revision_accession","revision_available_at","before","after","status"]).to_csv(O/"restatement_lineage.csv",index=False)
    pd.DataFrame(columns=["cik","field","fiscal_period","start","end","accession","derivation","status"]).to_csv(O/"financial_period_derivation.csv",index=False)
    pit=pd.read_csv(P103/"pit_time_audit.csv");pit.to_csv(O/"pit_availability_audit.csv",index=False)
    cov={"dataset_quarters":1,"dataset_rows":{"sub":len(sub),"num":len(num),"tag":len(tag),"pre":len(pre)},"aapl_total":len(idx),"aapl_matched":len(matched),"comparison_rows":len(comp),"cross_section":30,"cross_section_parsed":0,"historical_map_confidence":"CURRENT_ONLY","strategy_ready":False}
    (O/"p10_4_coverage.json").write_text(json.dumps(cov,indent=2),encoding="utf-8")
    status={"generated_at":datetime.now(timezone.utc).isoformat(),"status":"P10_4_SEC_DATASET_PARTIAL","dataset_downloaded":"2024q1","aapl_matched":len(matched),"aapl_unmatched_due_to_not_downloaded":65,"strategy_ready":False,"data_blocked":["65 AAPL filing quarters not downloaded","30-company accession parsing not done","delisted-inclusive CIK map","QTD/restatement lineage","exact publication timestamps"],"no_shadow":True,"note":"SEC data set is ingested and accession-linked for the downloaded quarter only; no claim of full AAPL or S&P coverage."}
    (O/"p10_4_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    print(json.dumps({"matched":matched,"comparison":reconciliation,"rows":{"sub":len(sub),"num":len(num)}},indent=2))


if __name__=="__main__":raise SystemExit(main())
