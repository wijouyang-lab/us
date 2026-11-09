"""P10.5 multi-period coverage and 30-company accession pilot."""
from __future__ import annotations
import csv,hashlib,json,re,time
from datetime import date,datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd,requests
from lxml import html

ROOT=Path(".");O=ROOT/"data/research/p10_5_sec_multi_period";O.mkdir(parents=True,exist_ok=True)
UA={"User-Agent":"us-pit-research/1.0 research@example.com"};CIK="0000320193";WANT={"Revenues","RevenueFromContractWithCustomerExcludingAssessedTax","SalesRevenueNet","GrossProfit","OperatingIncomeLoss","NetIncomeLoss","EarningsPerShareBasic","EarningsPerShareDiluted","Assets","Liabilities","CashAndCashEquivalentsAtCarryingValue","LongTermDebt","StockholdersEquity","NetCashProvidedByUsedInOperatingActivities","PaymentsToAcquirePropertyPlantAndEquipment","WeightedAverageNumberOfSharesOutstandingBasic","WeightedAverageNumberOfDilutedSharesOutstanding","CommonStockSharesOutstanding"}


def get(u):
    r=requests.get(u,headers=UA,timeout=60);r.raise_for_status();return r


def subs(cik):
    d=get(f"https://data.sec.gov/submissions/CIK{cik}.json").json();out=[];recent=d["filings"]["recent"]
    for i in range(len(recent["form"])):out.append({k:recent[k][i] for k in recent if recent[k] and i<len(recent[k])})
    for f in d["filings"].get("files",[]):
        x=get("https://data.sec.gov/submissions/"+f["name"]).json();rec=x.get("filings",{}).get("recent",x)
        for i in range(len(rec["form"])):out.append({k:rec[k][i] for k in rec if rec[k] and i<len(rec[k])})
    return out


def parse_inline(b):
    doc=html.fromstring(b);contexts={}
    for c in doc.xpath("//*[name()='xbrli:context']"):
        per=c.xpath(".//*[name()='xbrli:period']")
        if not per:continue
        p=per[0];st=p.xpath(".//*[name()='xbrli:startdate']");en=p.xpath(".//*[name()='xbrli:enddate']");ins=p.xpath(".//*[name()='xbrli:instant']")
        contexts[c.get("id")]={"start":st[0].text if st else None,"end":en[0].text if en else (ins[0].text if ins else None)}
    out=[]
    for f in doc.xpath("//*[name()='ix:nonfraction']"):
        short=(f.get("name") or "").split(":")[-1]
        if short not in WANT:continue
        try:v=float("".join(f.itertext()).strip().replace(",",""));v*=10**float(f.get("scale") or 0)
        except:continue
        ctx=contexts.get(f.get("contextRef") or f.get("contextref"),{});out.append((short,v,ctx.get("start"),ctx.get("end")))
    return out


def parse_sep(b):
    from lxml import etree
    root=etree.fromstring(b);contexts={}
    for c in root.xpath("//*[local-name()='context']"):
        per=c.xpath(".//*[local-name()='period']")
        if not per:continue
        p=per[0];st=p.xpath(".//*[local-name()='startDate']");en=p.xpath(".//*[local-name()='endDate']");ins=p.xpath(".//*[local-name()='instant']")
        contexts[c.get("id")]={"start":st[0].text if st else None,"end":en[0].text if en else (ins[0].text if ins else None)}
    out=[]
    for el in root.iter():
        if not isinstance(el.tag,str):continue
        q=etree.QName(el);short=q.localname
        if short not in WANT:continue
        try:v=float((el.text or "").replace(",",""))
        except:continue
        ctx=contexts.get(el.get("contextRef"),{});out.append((short,v,ctx.get("start"),ctx.get("end")))
    return out


def main():
    idx=pd.read_csv("data/research/p10_3_sec_xbrl_coverage/aapl_all_status.csv")
    def qtr(s):
        d=pd.Timestamp(s);return f"{d.year}q{(d.month-1)//3+1}"
    idx["dataset_quarter"]=idx.filing_date.map(qtr)
    idx["dataset_status"]="NOT_IN_DATASET"
    idx.loc[idx.dataset_quarter=="2024q1","dataset_status"]="NOT_MATCHED"
    idx.to_csv(O/"aapl_required_dataset_periods.csv",index=False)
    # dataset match from P10.4
    m=pd.read_csv("data/research/p10_4_sec_dataset_integration/sec_dataset_accession_match.csv")
    matched=set(m[m.dataset_match=="MATCHED"].accession)
    idx["dataset_status"]=[("DATASET_MATCHED" if a in matched else ("NOT_IN_DATASET" if q!="2024q1" else "DATASET_NO_NUM_FACTS")) for a,q in zip(idx.accession,idx.dataset_quarter)]
    idx.to_csv(O/"aapl_all_accession_match.csv",index=False)
    # 30-company current/historical-member sample; honest current-map bias
    mem=pd.read_csv("data/research/historical_universe/sp500_daily.csv",parse_dates=["date"]);last=mem.sort_values("date").iloc[-1]["tickers"];tickers=sorted({x.strip().upper() for x in str(last).split(",") if x.strip()})[:30]
    tick=requests.get("https://www.sec.gov/files/company_tickers.json",headers=UA,timeout=60).json();mp={v["ticker"].upper():f"{int(v['cik_str']):010d}" for v in tick.values()}
    allrows=[];facts=[];cov=[]
    for t in tickers:
        cik=mp.get(t)
        if not cik:cov.append({"ticker":t,"cik":"","status":"NO_CIK"});continue
        try:
            fs=subs(cik);ks=[x for x in fs if x["form"] in ("10-K","10-Q") and "2009-01-01"<=x.get("filingDate","")<="2024-12-31"]
            ks=sorted(ks,key=lambda x:x["filingDate"],reverse=True)
            tenks=[x for x in ks if x["form"]=="10-K"][:2];tenqs=[x for x in ks if x["form"]=="10-Q"][:2]
            sel=tenks+tenqs;parsed=0
            for f in sel:
                acc=f["accessionNumber"];accn=acc.replace("-","");url=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn}/{f.get('primaryDocument','')}"
                rec={"ticker":t,"cik":cik,"accession":acc,"form":f["form"],"filing_date":f["filingDate"],"acceptance_datetime":f.get("acceptanceDateTime"),"url":url,"status":""}
                try:
                    r=get(url);rec["sha256"]=hashlib.sha256(r.content).hexdigest()
                    if b"ix:nonfraction" in r.content:
                        ff=parse_inline(r.content);rec["format"]="INLINE"
                    else:
                        base=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn}";j=get(base+"/index.json").json();names=[x["name"] for x in j["directory"]["item"]];cand=[n for n in names if n.endswith(".xml") and not re.search(r"(_cal|_def|_lab|_pre|FilingSummary)",n)]
                        if not cand:rec["status"]="ORIGINAL_FILE_NO_XBRL";allrows.append(rec);continue
                        ff=parse_sep(get(base+"/"+cand[0]).content);rec["format"]="SEPARATE"
                    rec["facts"]=len(ff);rec["status"]="PARSED" if ff else "NO_CORE_FACTS";parsed+=1 if ff else 0
                    for x in ff:facts.append({"ticker":t,"accession":acc,"field":x[0],"value":x[1],"period_start":x[2],"period_end":x[3]})
                except Exception as e:rec["status"]="ERROR";rec["error"]=str(e)[:120]
                allrows.append(rec);time.sleep(0.1)
            cov.append({"ticker":t,"cik":cik,"selected":len(sel),"parsed":parsed,"tenk":len(tenks),"tenq":len(tenqs),"status":"PARTIAL" if parsed else "NO_PARSE"})
        except Exception as e:cov.append({"ticker":t,"cik":cik,"status":"SUBMISSION_ERROR","error":str(e)[:120]})
    pd.DataFrame(allrows).to_csv(O/"cross_section_30_accession_coverage.csv",index=False);pd.DataFrame(facts).to_csv(O/"cross_section_30_facts.csv",index=False);pd.DataFrame(cov).to_csv(O/"cross_section_30_field_coverage.csv",index=False)
    # field coverage per company
    fdf=pd.DataFrame(facts);rows=[]
    if len(fdf):
        for t,g in fdf.groupby("ticker"):
            for f in WANT:
                rows.append({"ticker":t,"field":f,"filings_with_field":g[g.field==f].accession.nunique(),"facts":int((g.field==f).sum())})
    pd.DataFrame(rows).to_csv(O/"cross_section_30_field_coverage.csv",index=False)
    status={"generated_at":datetime.now(timezone.utc).isoformat(),"status":"P10_5_SEC_MULTI_PERIOD_PARTIAL","aapl_total":len(idx),"aapl_dataset_matched":int((idx.dataset_status=="DATASET_MATCHED").sum()),"aapl_quarters":len(set(idx.dataset_quarter)),"companies":len(cov),"accessions_selected":len(allrows),"accessions_parsed":int(sum(1 for x in allrows if x["status"]=="PARSED")),"historical_delisted_companies":0,"dataset_quarters_downloaded":["2024q1"],"pit_status":"PIT_ACCEPTANCE_PROXY","strategy_ready":False,"data_blocked":["65 AAPL quarters not downloaded","historical delisted CIK mapping","30-company sample is current-map biased","QTD/YTD and restatement lineage not implemented","Notes data sets not ingested"],"no_shadow":True}
    (O/"p10_5_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    print(json.dumps(status,indent=2))


if __name__=="__main__":raise SystemExit(main())
