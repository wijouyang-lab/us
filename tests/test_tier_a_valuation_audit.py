import pandas as pd, math
from pathlib import Path
P=Path("artifacts/tier_a_30_diligence_audit")
def test_30_rows(): d=pd.read_csv(P/"ttm_metrics.csv"); assert len(d)==30 and d.ticker.nunique()==30
def test_ttm_identity():
 d=pd.read_csv(P/"ttm_metrics.csv"); x=d[d.ttm_method=="FY+YTD-PRIOR_YTD"]
 for c in ["revenue","net_income","ocf","capex"]:
  assert ((x[f"{c}_fy"]+x[f"{c}_ytd"]-x[f"{c}_prior_ytd"]-x[f"{c}_ttm"]).abs()<2).all()
def test_fy_as_ttm():
 d=pd.read_csv(P/"ttm_metrics.csv"); x=d[d.ttm_method=="FY_AS_TTM"]; assert set(x.ticker)=={"DHI","AMTM","WDFC","GSL"}
def test_fcf_identity():
 d=pd.read_csv(P/"ttm_metrics.csv"); x=d.dropna(subset=["ocf_ttm","capex_ttm","fcf_ttm"]); assert ((x.ocf_ttm-x.capex_ttm-x.fcf_ttm).abs()<2).all()
def test_no_zero_fill():
 d=pd.read_csv(P/"ttm_metrics.csv"); assert not d.pe_ttm.fillna(0).eq(0).any(); assert d.ev_fcf_ttm.isna().sum()>=2
def test_debt_methods():
 d=pd.read_csv(P/"balance_sheet_debt_audit.csv"); assert len(d)==30; assert d.method.fillna("N/A").isin(["TOTAL_TAG","SUM_COMPONENTS","N/A"]).all()
def test_market_cap():
 d=pd.read_csv(P/"ttm_metrics.csv"); x=d[(d.ticker!="NRDS")&d.shares.notna()]; assert ((x.price*x.shares-x.market_cap).abs()<3).all()
def test_dates():
 d=pd.read_csv(P/"ttm_metrics.csv"); assert d.price_date.eq("2026-11-25").all()
def test_period_audit():
 q=pd.read_csv(P/"quarter_period_audit.csv"); assert len(q)==120; assert q.ytd_days.dropna().ge(80).all()
def test_source_trace():
 s=pd.read_csv("artifacts/tier_a_30_diligence/source_register.csv"); assert len(s)==30 and s.url.notna().all()
