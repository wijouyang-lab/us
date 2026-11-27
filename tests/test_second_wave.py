import pandas as pd, math
from pathlib import Path
P=Path("artifacts/second_wave_watch_opportunity_screen_v1")
def test_25(): d=pd.read_csv(P/"candidate_universe.csv"); assert len(d)==25 and d.ticker.nunique()==25
def test_shortlist(): d=pd.read_csv(P/"candidate_universe.csv"); assert d.review_status.eq("SECOND_WAVE_RESEARCH").sum()==4; assert set(d[d.review_status=="SECOND_WAVE_RESEARCH"].ticker)=={"IMMR","OPRX","PHR","NATR"}
def test_watch(): d=pd.read_csv(P/"candidate_universe.csv"); assert d.decision.eq("WATCH").all()
def test_scenario(): s=pd.read_csv(P/"valuation_scenarios.csv"); assert len(s)==12; assert ((s.fcf*s.multiple-s.net_debt-s.equity).abs()<2).all()
def test_prices(): d=pd.read_csv(P/"candidate_universe.csv"); assert d[d.ticker!="SNDK"].price_date.eq("2026-11-25").all(); assert d[d.ticker=="SNDK"].price_date.iloc[0]=="2026-11-19"
def test_sources(): s=pd.read_csv(P/"source_register.csv"); assert len(s)==25 and s.url.notna().all()
def test_no_paper(): d=pd.read_csv(P/"candidate_universe.csv"); assert "PAPER_CANDIDATE" not in set(d.review_status)
