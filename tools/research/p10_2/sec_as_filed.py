"""P10.2 AAPL accession-level as-filed pilot + 30-company coverage probe."""
from __future__ import annotations
import csv,hashlib,json,time
from datetime import date,datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd, requests
from lxml import html

ROOT=Path(".");O=ROOT/"data/research/p10_2_sec_as_filed";O.mkdir(parents=True,exist_ok=True)
UA={"User-Agent":"us-pit-research/1.0 research@example.com"};CIK="0000320193"
WANT={"Revenues","RevenueFromContractWithCustomerExcludingAssessedTax","SalesRevenueNet","GrossProfit","OperatingIncomeLoss","NetIncomeLoss","EarningsPerShareDiluted","EarningsPerShareBasic","Assets","Liabilities","CashAndCashEquivalentsAtCarryingValue","LongTermDebt","StockholdersEquity","NetCashProvidedByUsedInOperatingActivities","PaymentsToAcquirePropertyPlantAndEquipment","WeightedAverageNumberOfDilutedSharesOutstanding","WeightedAverageNumberOfSharesOutstandingBasic","CommonStockSharesOutstanding"}
NS="{http://www.xbrl.org/2013/inlineXBRL}"


def get(url):
    r=requests.get(url,headers=UA,timeout=60);r.raise_for_status();return r


def submissions(cik):
    d=get(f"https://data.sec.gov/submissions/CIK{cik}.json").json();out=[]
    recent=d["filings"]["recent"]
    for i in range(len(recent["form"])):
        out.append({k:recent[k][i] for k in recent if recent[k] and i<len(recent[k])})
    for f in d["filings"].get("files",[]):
        x=get("https://data.sec.gov/submissions/"+f["name"]).json();rec=x["filings"]["recent"] if "filings" in x else x
        for i in range(len(rec["form"])):
            out.append({k:rec[k][i] for k in rec if rec[k] and i<len(rec[k])})
    return d,out


def parse_filing(content):
    doc=html.fromstring(content)
    contexts={}
    for c in doc.xpath("//*[name()='xbrli:context']"):
        cid=c.get("id");per=c.xpath(".//*[name()='xbrli:period']")
        if not per:continue
        p=per[0];st=p.xpath(".//*[name()='xbrli:startdate']");en=p.xpath(".//*[name()='xbrli:enddate']");ins=p.xpath(".//*[name()='xbrli:instant']")
        contexts[cid]={"start":st[0].text if st else None,"end":(en[0].text if en else (ins[0].text if ins else None))}
    facts=[]
    for f in doc.xpath("//*[name()='ix:nonfraction']"):
        name=f.get("name","");short=name.split(":")[-1]
        if short not in WANT:continue
        txt="".join(f.itertext()).strip().replace(",","")
        try:v=float(txt)
        except:continue
        sc=float(f.get("scale","0") or 0);v*=10**sc
        if f.get("sign")=="-":v=-v
        ctx=contexts.get(f.get("contextRef") or f.get("contextref"),{})
        facts.append({"concept":name,"field":short,"value":v,"unit":f.get("unitRef",""),"context":f.get("contextRef",""),"period_start":ctx.get("start"),"period_end":ctx.get("end")})
    return facts


def main():
    d,filings=submissions(CIK)
    chosen=[f for f in filings if f["form"] in ("10-K","10-Q","10-K/A","10-Q/A") and "2009-01-01"<=f.get("filingDate","")<="2024-12-31"]
    rows=[];allfacts=[];coverage=[]
    for f in chosen:
        acc=f["accessionNumber"];accn=acc.replace("-","");primary=f.get("primaryDocument","")
        url=f"https://www.sec.gov/Archives/edgar/data/{int(CIK)}/{accn}/{primary}"
        rec={"cik":CIK,"accession":acc,"form":f["form"],"filing_date":f.get("filingDate"),"acceptance_datetime":f.get("acceptanceDateTime"),"fiscal_year":f.get("fy"),"fiscal_period":f.get("fp"),"primary_document":primary,"url":url,"download_time":datetime.now(timezone.utc).isoformat(),"parser_version":"p10_2_inline_xbrl_v1"}
        try:
            r=get(url);rec["http"]=r.status_code;rec["sha256"]=hashlib.sha256(r.content).hexdigest();rec["bytes"]=len(r.content)
            facts=parse_filing(r.content);rec["facts"]=len(facts);rec["parse_status"]="PARSED" if facts else "NO_CORE_FACTS"
            for x in facts:allfacts.append({**rec,"**":None,**x})
        except Exception as e:
            rec["parse_status"]="DOWNLOAD_OR_PARSE_ERROR";rec["error"]=str(e)[:200]
        rows.append(rec);time.sleep(0.12)
    idx=pd.DataFrame(rows);idx.to_csv(O/"aapl_filings_index.csv",index=False)
    facts=pd.DataFrame(allfacts);facts.to_csv(O/"aapl_as_filed_facts.csv",index=False)
    # transaction-available time using acceptance UTC -> ET -> next SPY session
    spy=pd.read_csv("data/research/p9_2_benchmark_audit/spy_yf.csv",parse_dates=["Date"]);sessions=[x.date() for x in spy.Date]
    def avail(s):
        if not s:return None,None
        dt=datetime.fromisoformat(s.replace("Z","+00:00"));et=dt.astimezone(ZoneInfo("America/New_York"));d0=et.date()
        if et.hour<9 or (et.hour==9 and et.minute<30):
            for d in sessions:
                if d>=d0:return str(d),"PRE_OPEN"
        for d in sessions:
            if d>d0:return str(d),"DURING_OR_AFTER"
        return None,"UNKNOWN"
    idx["trade_available_date"]="";idx["timing_class"]=""
    for i,r in idx.iterrows():
        a,b=avail(r.acceptance_datetime);idx.at[i,"trade_available_date"]=a;idx.at[i,"timing_class"]=b
    idx.to_csv(O/"aapl_filings_index.csv",index=False)
    cov={"filings":len(idx),"parsed":int((idx.parse_status=="PARSED").sum()),"failed":int((idx.parse_status!="PARSED").sum()),"acceptance_present":int(idx.acceptance_datetime.notna().sum()),"trade_date_present":int((idx.trade_available_date!="").sum()),"forms":idx.form.value_counts().to_dict(),"facts":len(facts),"core_fields":sorted(set(facts.field)) if len(facts) else []}
    # 30-company deterministic coverage probe from current SEC map
    tick=requests.get("https://www.sec.gov/files/company_tickers.json",headers=UA,timeout=60).json()
    mp={v["ticker"].upper():f"{int(v['cik_str']):010d}" for v in tick.values()}
    mem=pd.read_csv("data/research/historical_universe/sp500_daily.csv");mem["date"]=pd.to_datetime(mem.date);last=mem[mem.date==mem.date.max()].iloc[0]["tickers"];tickers=sorted({x.strip() for x in str(last).split(",") if x.strip()})[:30]
    rows30=[]
    for t in tickers:
        cik=mp.get(t)
        if not cik:
            rows30.append({"ticker":t,"cik":"","status":"NO_CIK_MAPPING"});continue
        try:
            _,fs=submissions(cik);ks=[x for x in fs if x["form"] in ("10-K","10-Q") and "2009-01-01"<=x.get("filingDate","")<="2024-12-31"]
            rows30.append({"ticker":t,"cik":cik,"filings_10k_10q":len(ks),"first":min([x.get("filingDate","") for x in ks],default=""),"last":max([x.get("filingDate","") for x in ks],default=""),"status":"METADATA_ONLY"})
        except Exception as e:rows30.append({"ticker":t,"cik":cik,"status":"ERROR","error":str(e)[:120]})
    pd.DataFrame(rows30).to_csv(O/"cross_section_30.csv",index=False)
    cov["cross_section"]={"tickers":len(rows30),"with_cik":sum(1 for x in rows30 if x["cik"]),"metadata_only":sum(1 for x in rows30 if x["status"]=="METADATA_ONLY"),"note":"current SEC map, not a delisted-inclusive historical mapping"}
    (O/"p10_2_coverage.json").write_text(json.dumps(cov,indent=2),encoding="utf-8")
    status={"generated_at":datetime.now(timezone.utc).isoformat(),"status":"P10_2_SEC_AS_FILED_PARTIAL","aapl":{"filings":cov["filings"],"parsed":cov["parsed"],"facts":cov["facts"],"coverage":cov},"cross_section":cov["cross_section"],"strategy_ready":False,"data_blocked":["analyst consensus","news first publication","delisted-inclusive CIK mapping","full 30-company as-filed parsing","8-K item taxonomy"],"note":"AAPL accession-level inline XBRL parsed; 30-company probe is metadata-only and current-universe biased."}
    (O/"p10_2_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    print(json.dumps({"filings":cov["filings"],"parsed":cov["parsed"],"facts":cov["facts"],"forms":cov["forms"],"cross":cov["cross_section"]},indent=2))


if __name__=="__main__":raise SystemExit(main())
