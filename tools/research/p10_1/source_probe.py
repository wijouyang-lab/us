"""P10.1 free-source PIT availability probe. Network results are evidence, not PIT certification."""
from __future__ import annotations
import json, statistics
from datetime import datetime, timezone
from pathlib import Path
import requests

O=Path("data/research/p10_1_pit_sources");O.mkdir(parents=True,exist_ok=True)
UA={"User-Agent":"us-pit-research/1.0 research@example.com"}


def main():
    out={"generated_at":datetime.now(timezone.utc).isoformat(),"sample":"AAPL CIK0000320193","sources":{}}
    # SEC submissions: filingDate and acceptanceDateTime
    r=requests.get("https://data.sec.gov/submissions/CIK0000320193.json",headers=UA,timeout=30)
    s=r.json();recent=s["filings"]["recent"]
    forms={}
    for f,d,a in zip(recent["form"],recent["filingDate"],recent["acceptanceDateTime"]):
        forms[f]=forms.get(f,0)+1
    out["sources"]["sec_submissions"]={"http":r.status_code,"filing_rows":len(recent["form"]),"forms":forms,"latest_filing":recent["filingDate"][0],"acceptance_example":recent["acceptanceDateTime"][0],"has_acceptance_timestamp":bool(recent["acceptanceDateTime"])}
    # companyfacts
    r=requests.get("https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",headers=UA,timeout=60)
    cf=r.json();filed=[];facts=0
    for tax in cf.get("facts",{}).values():
        for f in tax.values():
            for unit in f.get("units",{}).values():
                for x in unit:
                    if x.get("filed"):filed.append(x["filed"]);facts+=1
    out["sources"]["sec_companyfacts"]={"http":r.status_code,"facts":facts,"filed_min":min(filed) if filed else None,"filed_max":max(filed) if filed else None,"has_accession":True,"note":"filed dates are available per fact; companyfacts is a current aggregate and may include amended/latest facts, not an as-filed point-in-time snapshot"}
    # Explicit blocks
    out["sources"]["analyst_estimates"]={"status":"DATA_BLOCKED","reason":"No free historical analyst-consensus snapshots with revision timestamps"}
    out["sources"]["news_first_publication"]={"status":"DATA_BLOCKED","reason":"No free archive verified to preserve first-publication timestamps; web pages are often updated"}
    out["sources"]["alfred_macro"]={"status":"DATA_BLOCKED","reason":"ALFRED vintage endpoint timed out in this environment; no verified vintage history or API key"}
    out["sources"]["repo_sec_cache"]={"status":"DATA_AVAILABLE_NOT_HISTORICAL","reason":"Repository SEC cache is current-period filings, not a 2000-2024 PIT panel"}
    (O/"probe_results.json").write_text(json.dumps(out,indent=2),encoding="utf-8")
    rows=[
        {"Source":"SEC submissions / filing metadata","Free access":"yes, no token","Historical coverage":"long filing history (sample latest only checked)","PIT availability":"YES for filingDate/acceptanceDateTime","Publication timestamp":"acceptanceDateTime","Revision history":"filing index is stable","Universe coverage":"SEC CIKs; ticker mapping separate","Missingness":"not measured for full universe","Reproducibility":"HTTP JSON","License":"public domain","Status":"PIT_VERIFIED_SAMPLE"},
        {"Source":"SEC Company Facts / XBRL","Free access":"yes, no token","Historical coverage":"sample filed dates available; usually 2009+","PIT availability":"PARTIAL","Publication timestamp":"filed date per fact, not exact acceptance time","Revision history":"current aggregate; amendments/restatements possible","Universe coverage":"SEC XBRL filers; history shorter","Missingness":"not measured","Reproducibility":"HTTP JSON","License":"public domain","Status":"PARTIAL"},
        {"Source":"SEC 10-K/10-Q as-filed XBRL","Free access":"yes","Historical coverage":"XBRL era only","PIT availability":"PARTIAL; requires accession-level parser","Publication timestamp":"submission acceptanceDateTime","Revision history":"accession-level possible","Universe coverage":"US filers, not 2000-2008","Missingness":"unknown","Reproducibility":"medium","License":"public domain","Status":"PARTIAL"},
        {"Source":"SEC 8-K events","Free access":"yes","Historical coverage":"filing metadata long history","PIT availability":"YES for filing timestamps; content extraction not done","Publication timestamp":"acceptanceDateTime","Revision history":"index","Universe coverage":"US filers","Missingness":"unknown","Reproducibility":"HTTP","License":"public domain","Status":"PARTIAL"},
        {"Source":"Analyst consensus / EPS surprise","Free access":"no free PIT snapshot","Historical coverage":"not available","PIT availability":"NO","Publication timestamp":"unknown","Revision history":"none","Universe coverage":"unknown","Missingness":"unknown","Reproducibility":"no","License":"restricted","Status":"DATA_BLOCKED"},
        {"Source":"News / corporate events first publication","Free access":"no reliable free archive","Historical coverage":"not verified","PIT availability":"NO","Publication timestamp":"not reliable","Revision history":"web updates overwrite","Universe coverage":"unknown","Missingness":"unknown","Reproducibility":"no","License":"restricted","Status":"DATA_BLOCKED"},
        {"Source":"Macro official releases / vintage","Free access":"ALFRED unreachable here; FRED current data not a vintage","Historical coverage":"unknown","PIT availability":"NO in this audit","Publication timestamp":"unknown","Revision history":"vintage API unverified","Universe coverage":"macro only","Missingness":"unknown","Reproducibility":"no","License":"public","Status":"DATA_BLOCKED"},
        {"Source":"ETF corporate actions / dividends","Free access":"yfinance actions","Historical coverage":"QQQ/SPY/BIL actions checked","PIT availability":"PARTIAL; vendor reported","Publication timestamp":"ex-date not first-announcement","Revision history":"none","Universe coverage":"ETFs only","Missingness":"small","Reproducibility":"vendor-dependent","License":"vendor terms","Status":"PARTIAL"},
    ]
    import csv
    with (O/"source_audit.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)
    status={"generated_at":out["generated_at"],"status":"P10_1_PIT_DATA_PARTIAL","sources_checked":len(rows),
            "data_available":True,"pit_verified":["SEC submissions metadata"],"coverage_verified":[],
            "strategy_ready":[],"next":"Probe SEC accession-level as-filed XBRL and 8-K metadata on a historical universe; do not claim analyst surprise without snapshots.",
            "blocks":["analyst consensus","news first publication","ALFRED vintage","full historical XBRL as-filed coverage"]}
    (O/"p10_1_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    print(json.dumps(status,indent=2))


if __name__=="__main__":raise SystemExit(main())
