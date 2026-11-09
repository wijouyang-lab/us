"""P10.3 recover AAPL old separate-XBRL filings and audit PIT availability."""
from __future__ import annotations
import csv,hashlib,json,re,time
from datetime import datetime,timezone,date
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd,requests
from lxml import etree

ROOT=Path(".");O=ROOT/"data/research/p10_3_sec_xbrl_coverage";O.mkdir(parents=True,exist_ok=True);P102=ROOT/"data/research/p10_2_sec_as_filed"
UA={"User-Agent":"us-pit-research/1.0 research@example.com"};CIK="0000320193"
WANT={"Revenues","RevenueFromContractWithCustomerExcludingAssessedTax","SalesRevenueNet","GrossProfit","OperatingIncomeLoss","NetIncomeLoss","EarningsPerShareDiluted","EarningsPerShareBasic","Assets","Liabilities","CashAndCashEquivalentsAtCarryingValue","LongTermDebt","StockholdersEquity","NetCashProvidedByUsedInOperatingActivities","PaymentsToAcquirePropertyPlantAndEquipment","WeightedAverageNumberOfDilutedSharesOutstanding","WeightedAverageNumberOfSharesOutstandingBasic","CommonStockSharesOutstanding"}


def get(u):
    r=requests.get(u,headers=UA,timeout=60);r.raise_for_status();return r


def parse_instance(content):
    root=etree.fromstring(content);facts=[];ctxmap={}
    for c in root.xpath("//*[local-name()='context']"):
        cid=c.get("id");per=c.xpath(".//*[local-name()='period']")
        if not per:continue
        p=per[0];st=p.xpath(".//*[local-name()='startDate']");en=p.xpath(".//*[local-name()='endDate']");ins=p.xpath(".//*[local-name()='instant']")
        ctxmap[cid]={"start":st[0].text if st else None,"end":(en[0].text if en else (ins[0].text if ins else None))}
    for el in root.iter():
        tag=etree.QName(el).localname if isinstance(el.tag,str) and etree.QName(el).namespace else ""
        if tag not in WANT:continue
        try:v=float((el.text or "").replace(",",""))
        except:continue
        ctx=ctxmap.get(el.get("contextRef"),{})
        facts.append({"field":tag,"value":v,"unit":el.get("unitRef",""),"context":el.get("contextRef",""),"period_start":ctx.get("start"),"period_end":ctx.get("end")})
    return facts


def main():
    idx=pd.read_csv(P102/"aapl_filings_index.csv");rows=[];facts=[];ledger=[]
    for r in idx.itertuples():
        rec={"cik":CIK,"accession":r.accession,"form":r.form,"filing_date":r.filing_date,"acceptance_datetime":r.acceptance_datetime,"trade_available_date":r.trade_available_date,"status":""}
        if r.parse_status=="PARSED":
            rec["status"]="INLINE_XBRL_PARSED";rows.append(rec);continue
        acc=r.accession.replace("-","");base=f"https://www.sec.gov/Archives/edgar/data/320193/{acc}"
        try:
            j=get(base+"/index.json").json();names=[x["name"] for x in j["directory"]["item"]]
        except Exception as e:
            rec["status"]="ORIGINAL_FILE_UNAVAILABLE";rec["error"]=str(e)[:120];rows.append(rec);continue
        cand=[n for n in names if n.endswith(".xml") and not re.search(r"(_cal|_def|_lab|_pre|FilingSummary|R\d+)",n) and not n.endswith(".xsd")]
        if not cand:
            rec["status"]="ORIGINAL_FILE_NO_XBRL";rows.append(rec);continue
        n=cand[0];url=base+"/"+n
        try:
            b=get(url).content;rec["instance_url"]=url;rec["sha256"]=hashlib.sha256(b).hexdigest();fs=parse_instance(b);rec["facts"]=len(fs);rec["status"]="SEPARATE_XBRL_PARSED" if fs else "DATA_INVALID"
            for x in fs:facts.append({**rec,**x})
        except Exception as e:
            rec["status"]="PARSER_UNSUPPORTED";rec["error"]=str(e)[:120]
        rows.append(rec);time.sleep(0.12)
    st=pd.DataFrame(rows);st.to_csv(O/"aapl_all_status.csv",index=False);fd=pd.DataFrame(facts);fd.to_csv(O/"separate_xbrl_facts.csv",index=False)
    # PIT availability proxy; no exact public visibility evidence
    spy=pd.read_csv("data/research/p9_2_benchmark_audit/spy_yf.csv",parse_dates=["Date"]);sessions=[x.date() for x in spy.Date]
    pit=[]
    for r in idx.itertuples():
        dt=datetime.fromisoformat(str(r.acceptance_datetime).replace("Z","+00:00"));et=dt.astimezone(ZoneInfo("America/New_York"))
        d0=et.date();A=next((d for d in sessions if d>=d0),None) if (et.hour<9 or (et.hour==9 and et.minute<30)) else next((d for d in sessions if d>d0),None)
        B=next((d for d in sessions if A and d>A),None)
        pit.append({"accession":r.accession,"accepted_at":str(dt),"accepted_et":str(et),"first_public_available_at":"","first_public_available_evidence":"","first_market_usable_A":str(A) if A else "","first_market_usable_B":str(B) if B else "","availability_status":"PIT_ACCEPTANCE_PROXY","note":"EDGAR acceptance is not exact public visibility; 1-3 min or more publication lag, no evidence captured"})
    pd.DataFrame(pit).to_csv(O/"pit_time_audit.csv",index=False)
    # 30-company metadata coverage (not full parsing)
    cs=pd.read_csv(P102/"cross_section_30.csv")
    cs["accession_parse_status"]="NOT_PARSED_IN_PILOT"
    cs.to_csv(O/"cross_section_30_status.csv",index=False)
    # dataset probe (HEAD only)
    ds_url="https://www.sec.gov/files/dera/data/financial-statement-data-sets/2024q1.zip"
    try:
        h=requests.head(ds_url,headers=UA,timeout=30);ds={"http":h.status_code,"content_length":h.headers.get("Content-Length"),"used":False,"status":"AVAILABLE_NOT_FETCHED" if h.status_code==200 else "UNAVAILABLE"}
    except Exception as e:ds={"status":"UNAVAILABLE","error":str(e)[:120],"used":False}
    cov={"filings":len(st),"status_counts":st.status.value_counts().to_dict(),"separate_facts":len(fd),"separate_fields":sorted(fd.field.unique().tolist()) if len(fd) else [],"cross_section":cs.status.value_counts().to_dict(),"dataset_probe":ds,"exact_publication_timestamp":False}
    (O/"p10_3_coverage.json").write_text(json.dumps(cov,indent=2),encoding="utf-8")
    status={"generated_at":datetime.now(timezone.utc).isoformat(),"status":"P10_3_SEC_XBRL_PARTIAL","aapl_status_counts":cov["status_counts"],"separate_facts":cov["separate_facts"],"strategy_ready":False,"data_blocked":["exact first public visibility","30-company full as-filed parse","delisted-inclusive CIK mapping","QTD/YTD/restatement lineage","SEC dataset full ingestion"],"note":"Old separate-XBRL instances recovered where present; acceptance is a PIT proxy, not a verified publication timestamp."}
    (O/"p10_3_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    print(json.dumps({"status_counts":cov["status_counts"],"separate_facts":len(fd),"fields":len(cov["separate_fields"]),"dataset":ds,"cross":cov["cross_section"]},indent=2))


if __name__=="__main__":raise SystemExit(main())
