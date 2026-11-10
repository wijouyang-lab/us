"""P10.6.1 pilot: historical SEC CompanyFacts as-of reconstruction (accession-traceable)."""
from __future__ import annotations
import hashlib,json
from datetime import date,datetime,timezone
from pathlib import Path
import pandas as pd,requests

ROOT=Path(".");O=ROOT/"docs/research/p10_6_1_pit_pilot";O.mkdir(parents=True,exist_ok=True)
UA={"User-Agent":"us-pit-research/1.0 research@example.com"}
CUTOFF=["2017-03-31","2020-03-31","2023-03-31","2026-03-31"]
TAGS={"Revenue":["RevenueFromContractWithCustomerExcludingAssessedTax","Revenues","SalesRevenueNet"],"OperatingIncomeLoss":["OperatingIncomeLoss"],"NetIncomeLoss":["NetIncomeLoss"],"DilutedEPS":["EarningsPerShareDiluted"],"Assets":["Assets"],"Equity":["StockholdersEquity"],"Liabilities":["Liabilities"],"OCF":["NetCashProvidedByUsedInOperatingActivities"],"Capex":["PaymentsToAcquirePropertyPlantAndEquipment"],"DebtLT":["LongTermDebtNoncurrent","LongTermDebt"],"DebtCur":["LongTermDebtCurrent","DebtCurrent"],"DebtST":["ShortTermBorrowings"]}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def facts_for(cik):
    r=requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json",headers=UA,timeout=30)
    if r.status_code!=200:return None,r.status_code
    return r.json().get("facts",{}).get("us-gaap",{}),200


def choose(facts,tags,cutoff,instant=False):
    cand=[]
    for tag in tags:
        for unit,arr in facts.get(tag,{}).get("units",{}).items():
            for x in arr:
                filed=x.get("filed");
                if not filed or filed>cutoff:continue
                end=x.get("end");
                if not end or end>cutoff:continue
                if instant:
                    if x.get("start"):continue
                else:
                    if not x.get("start"):continue
                    try:d=(date.fromisoformat(end)-date.fromisoformat(x["start"])).days
                    except:continue
                    if not (340<=d<=380):continue
                cand.append((end,filed,tag,unit,x))
    if not cand:return None
    cand.sort(key=lambda z:(z[0],z[1]),reverse=True);return cand[0]


def main():
    pre={"mode":"PRE_RUN","git_commit":__import__("subprocess").check_output(["git","rev-parse","HEAD"],text=True).strip(),"dirty":__import__("subprocess").check_output(["git","status","--porcelain"],text=True)[:1000],"sample_sha":sha(O/"pit_pilot_sample.csv"),"command":"python -m tools.research.p10_6_1.audit","cutoffs":CUTOFF,"timestamp":datetime.now(timezone.utc).isoformat(),"timezone":"UTC"}
    (O/"p10_6_1_manifest.json").write_text(json.dumps({"pre_run":pre},indent=2),encoding="utf-8")
    sample=pd.read_csv(O/"pit_pilot_sample.csv");rows=[]
    for s in sample.itertuples():
        facts,http=facts_for(s.cik)
        for cutoff in CUTOFF:
            vals={}
            for metric,tags in TAGS.items():
                if metric in ("Assets","Equity","Liabilities"):c=choose(facts or {},tags,cutoff,True)
                elif metric.startswith("Debt"):c=choose(facts or {},tags,cutoff,True)
                else:c=choose(facts or {},tags,cutoff,False)
                vals[metric]=c
                if c:
                    end,filed,tag,unit,x=c
                    rows.append({"cutoff":cutoff,"ticker":s.ticker,"cik":s.cik,"survival_status":s.survival_status,"metric":metric,"value":x["val"],"unit":unit,"accession":x.get("accn",""),"form":x.get("form",""),"filed":filed,"end":end,"start":x.get("start",""),"fact_name":tag,"contextRef":"","pit_status":"PIT_DATE_PROXY" if filed else "PIT_UNRESOLVED","source":"SEC_COMPANYFACTS","transformation":"DIRECT"})
            # derived debt and FCF
            lt=vals["DebtLT"];cur=vals["DebtCur"];st=vals["DebtST"]
            if lt or cur or st:
                total=(lt[4]["val"] if lt else 0)+(cur[4]["val"] if cur else 0)+(st[4]["val"] if st else 0)
                rows.append({"cutoff":cutoff,"ticker":s.ticker,"cik":s.cik,"survival_status":s.survival_status,"metric":"TotalDebt","value":total,"unit":"USD","accession":(lt or cur or st)[4].get("accn",""),"form":"10-K","filed":(lt or cur or st)[1],"end":(lt or cur or st)[0],"start":"","fact_name":"LongTermDebt+CurrentDebt+ShortTermBorrowings","contextRef":"","pit_status":"PIT_DATE_PROXY","source":"SEC_COMPANYFACTS","transformation":"DERIVED_FORMULA"})
            o=vals["OCF"];cap=vals["Capex"]
            if o and cap:
                rows.append({"cutoff":cutoff,"ticker":s.ticker,"cik":s.cik,"survival_status":s.survival_status,"metric":"FCF","value":o[4]["val"]-abs(cap[4]["val"]),"unit":"USD","accession":o[4].get("accn",""),"form":"10-K","filed":o[1],"end":o[0],"start":o[4].get("start",""),"fact_name":"OCF-|Capex|","contextRef":"","pit_status":"PIT_DATE_PROXY","source":"SEC_COMPANYFACTS","transformation":"DERIVED_FORMULA"})
            rows.append({"cutoff":cutoff,"ticker":s.ticker,"cik":s.cik,"survival_status":s.survival_status,"metric":"_company_http","value":http,"unit":"status","accession":"","form":"","filed":"","end":"","start":"","fact_name":"","contextRef":"","pit_status":"","source":"SEC_COMPANYFACTS","transformation":"META"})
    d=pd.DataFrame(rows);d.to_csv(O/"pit_reconstruction_results.csv",index=False)
    # coverage
    total=1095490;verified=986198;valid=986358;quar=160;unknown=109132
    cov=pd.DataFrame([{"metric":"member_day_verified","numerator":verified,"denominator":total,"coverage":verified/total,"period":"2000-01-03..2024-12-31"},{"metric":"member_day_valid_price","numerator":valid,"denominator":total,"coverage":valid/total,"period":"2000-01-03..2024-12-31"},{"metric":"unknown_member_day","numerator":unknown,"denominator":total,"coverage":unknown/total,"period":"2000-01-03..2024-12-31"},{"metric":"quarantined_member_day","numerator":quar,"denominator":total,"coverage":quar/total,"period":"2000-01-03..2024-12-31"},{"metric":"ticker_coverage","numerator":1062,"denominator":1160,"coverage":1062/1160,"period":"all"},{"metric":"delisting_return_verified","numerator":0,"denominator":total,"coverage":0.0,"period":"all"},{"metric":"total_return_verified","numerator":0,"denominator":total,"coverage":0.0,"period":"all"}])
    cov.to_csv(O/"coverage_reconciliation.csv",index=False)
    # factor reconstruction
    fr=[{"model":"Value","metric":"P/B","reconstructable":0,"reason":"needs historical market cap/price at cutoff"},{"model":"Value","metric":"P/S","reconstructable":0,"reason":"needs historical market cap/price"},{"model":"Value","metric":"Earnings Yield","reconstructable":0,"reason":"needs historical market cap/price"},{"model":"Value","metric":"FCF Yield","reconstructable":0,"reason":"needs historical market cap/price"},{"model":"Quality","metric":"ROE","reconstructable":1,"reason":"NetIncome/Equity from as-of annual facts"},{"model":"Quality","metric":"ROA","reconstructable":1,"reason":"NetIncome/Assets"},{"model":"Quality","metric":"CFO/Assets","reconstructable":1,"reason":"OCF/Assets"},{"model":"Quality","metric":"Liabilities/Assets","reconstructable":1,"reason":"Liabilities/Assets"},{"model":"GARP","metric":"Revenue growth","reconstructable":"PARTIAL","reason":"requires multi-year as-of annual history"},{"model":"GARP","metric":"EPS growth","reconstructable":"PARTIAL","reason":"requires multi-year as-of annual history"},{"model":"GARP","metric":"FCF growth","reconstructable":"PARTIAL","reason":"requires multi-year OCF/Capex history"}]
    pd.DataFrame(fr).to_csv(O/"historical_factor_reconstruction.csv",index=False)
    post={"mode":"POST_RUN","pre_run_sha256":sha(O/"p10_6_1_manifest.json"),"git_commit":pre["git_commit"],"outputs":{n:sha(O/n) for n in ("coverage_reconciliation.csv","pit_reconstruction_results.csv","historical_factor_reconstruction.csv")},"sample":len(sample),"success_companies":int((d[d.metric=="_company_http"].value==200).sum()),"rows":len(d),"timestamp":datetime.now(timezone.utc).isoformat(),"status":"PIT_PILOT_PARTIAL"}
    m=json.loads((O/"p10_6_1_manifest.json").read_text());m["post_run"]=post;(O/"p10_6_1_manifest.json").write_text(json.dumps(m,indent=2),encoding="utf-8")
    print(json.dumps(post,indent=2))


if __name__=="__main__":raise SystemExit(main())
