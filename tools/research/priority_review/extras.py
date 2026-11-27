import json, hashlib
from pathlib import Path
import pandas as pd
ROOT=Path(r"C:\Users\ouyan\Documents\deepseek-harness\_priority")
OUT=Path(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_priority_review")
DATA=Path(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_priority_data")
m=pd.read_csv(OUT/"investment_decisions.csv")
b=pd.read_csv(OUT/"business.csv")
m=m.drop(columns=[c for c in m.columns if c.startswith("business") or c.startswith("src_") or c in ("form","period","url","filing_date")],errors="ignore").merge(b,on="ticker",how="left")
# source register latest 10-K/10-Q
src=[]
for t in m.ticker:
    try:
        s=json.load(open(DATA/f"{t}_subs.json")); r=s["filings"]["recent"]
        for i,f in enumerate(r["form"]):
            if f in ("10-K","10-Q"):
                acc=r["accessionNumber"][i].replace("-",""); cik=int(s["cik"])
                url=f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{r['primaryDocument'][i]}"
                src.append({"ticker":t,"form":f,"period":r["reportDate"][i],"filing_date":r["filingDate"][i],"accession":r["accessionNumber"][i],"url":url,"source":"SEC EDGAR"})
                break
    except Exception: pass
sd=pd.DataFrame(src); sd.to_csv(OUT/"source_register.csv",index=False)
sd=sd.rename(columns={"form":"src_form","period":"src_period","filing_date":"src_filing_date","accession":"src_accession","url":"src_url","source":"src_source"})
m=m.merge(sd,on="ticker",how="left")
m.to_csv(OUT/"investment_decisions.csv",index=False)
# dossier
L=["# Priority 39 — Company Dossiers","","Prices 2026-11-25; TTM from SEC XBRL; research only, not buy/sell.",""]
for _,x in m.sort_values("decision").iterrows():
    L += [f"## {x.ticker} — {x.company}",f"",f"**Decision: {x.decision}**  ",f"**Style(s): {x.all_styles}**  ",
          f"**Business:** {x.business}","",
          f"**Financials (TTM):** revenue {x.revenue_ttm if pd.notna(x.revenue_ttm) else 'N/A'}; net income {x.net_income_ttm if pd.notna(x.net_income_ttm) else 'N/A'}; OCF {x.ocf_ttm if pd.notna(x.ocf_ttm) else 'N/A'}; capex {x.capex_ttm if pd.notna(x.capex_ttm) else 'N/A'}; FCF {x.fcf_ttm if pd.notna(x.fcf_ttm) else 'N/A'}.","",
          f"**Valuation:** P/E {x.pe_ttm if pd.notna(x.pe_ttm) else 'N/A'}; EV/FCF {x.ev_fcf_ttm if pd.notna(x.ev_fcf_ttm) else 'N/A'}; FCF yield {x.fcf_yield_ttm if pd.notna(x.fcf_yield_ttm) else 'N/A'}; net debt {x.net_debt if pd.notna(x.net_debt) else 'N/A'}.","",
          f"**Decision reason:** {x.decision_reason}.","",
          f"**Filing:** {x.src_form if pd.notna(x.src_form) else 'N/A'} period {x.src_period if pd.notna(x.src_period) else 'N/A'} filed {x.src_filing_date if pd.notna(x.src_filing_date) else 'N/A'}; [SEC]({x.src_url if pd.notna(x.src_url) else 'N/A'}).","",
          "**Why it may be a trap / invalidation:** verify cash conversion, one-off items, leverage, customer concentration, and whether the screen percentile is driven by a single period. If FCF is negative/NA or valuation is N/A, the decision remains WATCH/INSUFFICIENT.",""]
(OUT/"company_dossiers.md").write_text("\n".join(L),encoding="utf-8")
# exec
cnt=m.decision.value_counts().to_dict()
E=["# Priority 39 — Investment Review Summary","","Date: 2026-11-27. Research only; no PAPER/IBKR/orders.","",
f"## Decisions","",f"- ELIMINATE: {cnt.get('ELIMINATE',0)}",f"- WATCH: {cnt.get('WATCH',0)}",f"- PRIORITY_WATCH: {cnt.get('PRIORITY_WATCH',0)}",f"- PAPER_CANDIDATE: 0",f"- INSUFFICIENT_DATA: {cnt.get('INSUFFICIENT_DATA',0)}","",
"## Priority watch",""]
for _,x in m[m.decision=="PRIORITY_WATCH"].iterrows(): E.append(f"- **{x.ticker}** — {x.company}; {x.decision_reason}; P/E {x.pe_ttm if pd.notna(x.pe_ttm) else 'N/A'}, EV/FCF {x.ev_fcf_ttm if pd.notna(x.ev_fcf_ttm) else 'N/A'}, net debt {x.net_debt if pd.notna(x.net_debt) else 'N/A'}.")
E += ["","## Eliminated",""]
for _,x in m[m.decision=="ELIMINATE"].iterrows(): E.append(f"- **{x.ticker}** — {x.decision_reason}.")
E += ["","## Insufficient data",""]
for _,x in m[m.decision=="INSUFFICIENT_DATA"].iterrows(): E.append(f"- **{x.ticker}** — {x.decision_reason}.")
E += ["","## Important data caveats","","- 39 unique tickers from 40 priority rows (CRMD appears in GARP and VALUE).","- 195 of 28,000 ticker/style combinations are DATA_UNAVAILABLE; full ledger included.","- Screen candidates include PARTIAL/UNKNOWN; only top 10/style required VERIFIED for priority.","- No PAPER candidate; no position.","- CRMD historical ELIMINATE override applied.",""]
(OUT/"executive_summary.md").write_text("\n".join(E),encoding="utf-8")
# coverage
cov=pd.read_csv(OUT/"candidate_accounting_28000.csv"); dq=pd.read_csv(OUT/"data_quality_reconciliation.csv")
C=["# Coverage Report — Priority 39","",f"28,000 ledger rows; status: {cov.status.value_counts().to_dict()}","", "## Candidate quality by style","", "| Style | VERIFIED | PARTIAL | UNKNOWN |","|---|---:|---:|---:|"]
for st in ["VALUE","QUALITY","GARP","TREND","TURNAROUND"]:
 x=dq[dq.style==st].set_index("data_quality")
 C.append(f"| {st} | {int(x.loc['VERIFIED','unique_tickers']) if 'VERIFIED' in x.index else 0} | {int(x.loc['PARTIAL','unique_tickers']) if 'PARTIAL' in x.index else 0} | {int(x.loc['UNKNOWN','unique_tickers']) if 'UNKNOWN' in x.index else 0} |")
C += ["","## Decision coverage","",f"- Reviewed unique tickers: {len(m)}",f"- Decisions: {cnt}",f"- Paper candidates: 0",""]
(OUT/"coverage_report.md").write_text("\n".join(C),encoding="utf-8")
print(len(m),cnt)
