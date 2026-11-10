"""P10.6 preflight audit: reuse existing artifacts, no network, no strategy."""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd

ROOT=Path(".");O=ROOT/"docs/research/p10_6_preflight";O.mkdir(parents=True,exist_ok=True)
SEL=ROOT/"data/universe/selection";P82=ROOT/"data/research/p8_2"


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    pre={"mode":"PRE_RUN","git_commit":__import__("subprocess").check_output(["git","rev-parse","HEAD"],text=True).strip(),"dirty":__import__("subprocess").check_output(["git","status","--porcelain"],text=True)[:1000],"inputs":{"value_rankings":sha(SEL/"value_rankings.csv"),"quality_rankings":sha(SEL/"quality_rankings.csv"),"garp_rankings":sha(SEL/"garp_rankings.csv"),"pit_summary":sha(P82/"pit_coverage_summary.json")},"command":"python -m tools.research.p10_6_preflight.audit","timestamp":datetime.now(timezone.utc).isoformat(),"timezone":"UTC"}
    (O/"p10_6_preflight_manifest.json").write_text(json.dumps({"pre_run":pre},indent=2),encoding="utf-8")
    rows=[]
    for name,file,metrics in (("Value","value_rankings.csv",["P/B","P/S","Earnings Yield","FCF Yield"]),("Quality","quality_rankings.csv",["ROE","ROA","CFO/Assets","Liabilities/Assets"]),("GARP","garp_rankings.csv",["Revenue growth","EPS growth","FCF growth","Earnings stability","Operating margin expansion","Operating leverage"])):
        d=pd.read_csv(SEL/file);asof=d.data_as_of.astype(str).nunique() if "data_as_of" in d else 0
        status="DATA_BLOCKED"
        if name=="Value":reason="single 2026-11-05 snapshot; no historical as-of panel; market cap tied to snapshot price"
        elif name=="Quality":reason="single 2026-11-05 snapshot; no historical as-of panel; filed/accn exist but only one cross-section"
        else:reason="no data_as_of field; latest period only; no historical GARP snapshots"
        rows.append({"model":name,"candidates":len(d),"top50":50,"metrics":len(metrics),"metric_names":";".join(metrics),"source":"SEC CompanyFacts/XBRL + snapshot market data","financial_period":str(d.financial_period.iloc[0]) if "financial_period" in d else str(d.latest_period.iloc[0]) if "latest_period" in d else "UNKNOWN","pit_status":"PIT_ACCEPTANCE_PROXY" if "accn" in d else "NOT_PIT","asof_snapshots":asof,"accession_present":bool("accn" in d),"lookahead_risk":"HIGH","status":status,"blocking_reason":reason})
    pd.DataFrame(rows).to_csv(O/"fundamental_factor_readiness.csv",index=False)
    universe=[{"universe":"S&P 500 effective-dated member-days 2000-2024","member_days":1095490,"verified_member_days":986198,"unknown_member_days":109132,"coverage":0.9002346,"threshold":0.95,"missing_tickers_previously_identified":98,"status":"DATA_BLOCKED","reason":"coverage 90.02% < 95%; historical delisted/common-stock universe not complete"}]
    pd.DataFrame(universe).to_csv(O/"historical_universe_readiness.csv",index=False)
    price=[{"universe":"S&P 500 historical members","price_coverage":0.9002346,"delisting_return_verified":False,"split_adjusted":True,"dividend_total_return":False,"missing_or_unverified_member_days":109132,"status":"DATA_BLOCKED","reason":"no verified delisting-return coverage; 9.96% member-days unknown; cannot compute usable post-selection returns for all names"}]
    pd.DataFrame(price).to_csv(O/"historical_price_readiness.csv",index=False)
    post={"mode":"POST_RUN","pre_run_sha256":sha(O/"p10_6_preflight_manifest.json"),"git_commit":pre["git_commit"],"outputs":{n:sha(O/n) for n in ("fundamental_factor_readiness.csv","historical_universe_readiness.csv","historical_price_readiness.csv")},"status":"DATA_BLOCKED","model_status":{"Value":"DATA_BLOCKED","Quality":"DATA_BLOCKED","GARP":"DATA_BLOCKED"},"timestamp":datetime.now(timezone.utc).isoformat()}
    m=json.loads((O/"p10_6_preflight_manifest.json").read_text());m["post_run"]=post;(O/"p10_6_preflight_manifest.json").write_text(json.dumps(m,indent=2),encoding="utf-8")
    print(json.dumps({"models":rows,"universe":universe,"price":price},indent=2))


if __name__=="__main__":raise SystemExit(main())
