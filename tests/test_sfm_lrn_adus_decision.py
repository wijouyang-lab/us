import pandas as pd
from pathlib import Path
P=Path("artifacts/sfm_lrn_adus_investment_decision")
def test_three(): d=pd.read_csv(P/"investment_comparison.csv"); assert len(d)==9
def test_quarters(): q=pd.read_csv(P/"quarterly_financials.csv"); assert len(q)==24 and q.groupby("ticker").size().eq(8).all()
def test_scenarios(): v=pd.read_csv(P/"valuation_scenarios.csv"); assert len(v)==9 and (v.implied_price>0).all()
def test_risks(): r=pd.read_csv(P/"risk_register.csv"); assert len(r)==30 and set(r.ticker)=={"SFM","LRN","ADUS"}
def test_sources(): s=pd.read_csv(P/"source_register.csv"); assert len(s)==6 and s.url.notna().all()
def test_decisions():
 d=pd.read_csv(P/"investment_comparison.csv")
 row=d[d.metric=="decision"].iloc[0]
 assert set([row.SFM,row.LRN,row.ADUS])=={"WATCH"}
