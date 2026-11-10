"""P10.6.3 build 60-name Technology/US_GAAP Quality cohort and score as-of cutoffs."""
from __future__ import annotations
import hashlib,json
from datetime import date,datetime,timezone
from pathlib import Path
import numpy as np,pandas as pd,requests

ROOT=Path(".");O=ROOT/"docs/research/p10_6_3_quality_expansion";O.mkdir(parents=True,exist_ok=True)
UA={"User-Agent":"us-pit-research/1.0 research@example.com"}
CUTOFF=["2017-03-31","2020-03-31","2023-03-31","2026-03-31"]
TAGS={"NetIncomeLoss":["NetIncomeLoss"],"Equity":["StockholdersEquity"],"Assets":["Assets"],"OCF":["NetCashProvidedByUsedInOperatingActivities"],"Liabilities":["Liabilities"]}
W={"roe":.30,"roa":.25,"cfo":.25,"leverage":.20}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def select_cohort():
    q=pd.read_csv("data/universe/selection/quality_rankings.csv")
    d=q[(q.model_family=="TECHNOLOGY")&(q.accounting_standard=="US_GAAP")&(q.security_type.isin(["COMMON","ADR"]))].drop_duplicates("cik")
    d=d.sort_values("cik");rows=d.head(60).copy()
    if "XLNX" not in set(rows.ticker):
        xl=pd.DataFrame([{"ticker":"XLNX","cik":743988,"company_name":"XILINX INC","model_family":"TECHNOLOGY","accounting_standard":"US_GAAP"}])
        rows=pd.concat([rows.head(59),xl],ignore_index=True)
    rows["cohort_role"]="TECH_US_GAAP_60"
    rows=rows[["ticker","cik","company_name","model_family","accounting_standard","cohort_role"]]
    rows.to_csv(O/"quality_peer_cohort.csv",index=False)
    return rows


def load_facts(cik):
    r=requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json",headers=UA,timeout=30)
    return (r.json().get("facts",{}).get("us-gaap",{}) if r.status_code==200 else {}),r.status_code


def choose(facts,tags,cutoff,instant):
    c=[]
    for tag in tags:
        for unit,arr in facts.get(tag,{}).get("units",{}).items():
            for x in arr:
                f=x.get("filed");e=x.get("end")
                if not f or not e or f>cutoff or e>cutoff:continue
                if instant and x.get("start"):continue
                if not instant:
                    if not x.get("start"):continue
                    try:days=(date.fromisoformat(e)-date.fromisoformat(x["start"])).days
                    except:continue
                    if not 340<=days<=380:continue
                c.append((e,f,tag,unit,x))
    if not c:return None
    c.sort(key=lambda z:(z[0],z[1]),reverse=True);return c[0]


def main():
    pre={"mode":"PRE_RUN","git_commit":__import__("subprocess").check_output(["git","rev-parse","HEAD"],text=True).strip(),"inputs":{"quality_rankings":sha("data/universe/selection/quality_rankings.csv")},"command":"python -m tools.research.p10_6_3.build","cutoffs":CUTOFF,"timestamp":datetime.now(timezone.utc).isoformat(),"timezone":"UTC"}
    (O/"p10_6_3_manifest.json").write_text(json.dumps({"pre_run":pre},indent=2),encoding="utf-8")
    co=select_cohort();rows=[];lin=[]
    for s in co.itertuples():
        facts,http=load_facts(s.cik)
        for cutoff in CUTOFF:
            vals={}
            for m,tags in TAGS.items():
                c=choose(facts,tags,cutoff,m in ("Assets","Equity","Liabilities"));vals[m]=c
                if c:
                    e,f,tag,unit,x=c;lin.append({"cutoff":cutoff,"ticker":s.ticker,"metric":m,"accession":x.get("accn",""),"fact_name":tag,"value":x["val"],"unit":unit,"filed":f,"period_end":e,"contextRef":"","raw_xbrl_verified":False,"pit_status":"PIT_DATE_PROXY"})
            ni=vals["NetIncomeLoss"][4]["val"] if vals["NetIncomeLoss"] else None
            eq=vals["Equity"][4]["val"] if vals["Equity"] else None
            at=vals["Assets"][4]["val"] if vals["Assets"] else None
            ocf=vals["OCF"][4]["val"] if vals["OCF"] else None
            lb=vals["Liabilities"][4]["val"] if vals["Liabilities"] else None
            roe=ni/eq if ni is not None and eq not in (None,0) else np.nan
            roa=ni/at if ni is not None and at not in (None,0) else np.nan
            cfo=ocf/at if ocf is not None and at not in (None,0) else np.nan
            lev=lb/at if lb is not None and at not in (None,0) else np.nan
            rows.append({"cutoff":cutoff,"ticker":s.ticker,"cik":s.cik,"company_name":s.company_name,"model_family":s.model_family,"accounting_standard":s.accounting_standard,"net_income":ni,"equity":eq,"assets":at,"ocf":ocf,"liabilities":lb,"roe":roe,"roa":roa,"cfo_to_assets":cfo,"liabilities_to_assets":lev,"company_http":http})
    panel=pd.DataFrame(rows);panel.to_csv(O/"quality_historical_panel.csv",index=False);pd.DataFrame(lin).to_csv(O/"quality_factor_lineage.csv",index=False)
    # scores per cutoff/group
    scores=[];stats=[]
    for cutoff,g in panel.groupby("cutoff"):
        for (mf,acc),h in g.groupby(["model_family","accounting_standard"]):
            metrics={"roe":"roe","roa":"roa","cfo":"cfo_to_assets","leverage":"liabilities_to_assets"}
            ok=h.dropna(subset=list(metrics.values()))
            n=len(ok)
            if n<30:
                for r in h.itertuples():scores.append({"cutoff":cutoff,"ticker":r.ticker,"quality_score_v1":np.nan,"quality_rank_v1":np.nan,"peer_count":n,"scoring_status":"NOT_SCORED_PEER_GROUP_TOO_SMALL"})
                stats.append({"cutoff":cutoff,"peer_count":n,"scored":0,"status":"NOT_SCORED_PEER_GROUP_TOO_SMALL"});continue
            pct={}
            for m,f in metrics.items():
                vals=ok[f].astype(float).tolist();lo,hi=np.percentile(vals,[1,99]);cl=np.clip(vals,lo,hi)
                p=pd.Series(cl).rank(pct=True,method="average")*100
                p=100-p if m=="leverage" else p
                pct[m]=p.tolist()
            sc=sum(np.array(pct[m])*W[m] for m in W)
            ok=ok.copy();ok["score"]=sc
            ok=ok.sort_values(["score","ticker"],ascending=[False,True]).reset_index(drop=True)
            for i,r in ok.iterrows():
                scores.append({"cutoff":cutoff,"ticker":r.ticker,"roe_percentile":pct["roe"][i],"roa_percentile":pct["roa"][i],"cfo_percentile":pct["cfo"][i],"leverage_percentile":pct["leverage"][i],"quality_score_v1":float(r.score),"quality_rank_v1":i+1,"peer_count":n,"scoring_status":"PILOT_SAMPLE_RANKING"})
            stats.append({"cutoff":cutoff,"peer_count":n,"scored":n,"status":"PILOT_SAMPLE_RANKING"})
    pd.DataFrame(scores).to_csv(O/"quality_historical_scores.csv",index=False);pd.DataFrame(stats).to_csv(O/"quality_peer_stats.csv",index=False)
    # context validation placeholder: not run
    pd.DataFrame([{"check":"raw_xbrl_contextRef_verified","count":0,"status":"NOT_RUN"}]).to_csv(O/"quality_xbrl_context_validation.csv",index=False)
    pd.DataFrame([{"check":"10K/A_replay","count":0,"status":"NOT_RUN"}]).to_csv(O/"quality_amendment_replay.csv",index=False)
    post={"mode":"POST_RUN","pre_run_sha256":sha(O/"p10_6_3_manifest.json"),"git_commit":pre["git_commit"],"outputs":{n:sha(O/n) for n in ("quality_peer_cohort.csv","quality_historical_panel.csv","quality_historical_scores.csv","quality_factor_lineage.csv","quality_xbrl_context_validation.csv","quality_amendment_replay.csv","quality_peer_stats.csv")},"cohort":len(co),"panel_rows":len(panel),"status":"QUALITY_PILOT_RANKING_READY" if any(x["status"]=="PILOT_SAMPLE_RANKING" for x in stats) else "QUALITY_PILOT_PARTIAL","stats":stats,"timestamp":datetime.now(timezone.utc).isoformat()}
    m=json.loads((O/"p10_6_3_manifest.json").read_text());m["post_run"]=post;(O/"p10_6_3_manifest.json").write_text(json.dumps(m,indent=2),encoding="utf-8")
    print(json.dumps(post,indent=2))


if __name__=="__main__":raise SystemExit(main())
