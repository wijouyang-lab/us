import pandas as pd, math
from pathlib import Path
P=Path("artifacts/sfm_lrn_adus_final_validation")
def test_formula():
 d=pd.read_csv(P/"corrected_valuation_scenarios.csv"); assert ((d.fcf*d.ev_fcf_multiple-d.net_debt-d.equity_value).abs()<2).all()
def test_share_consistency():
 d=pd.read_csv(P/"corrected_valuation_scenarios.csv"); assert d.groupby("ticker").diluted_shares.nunique().eq(1).all()
def test_netcash_sign():
 d=pd.read_csv(P/"corrected_valuation_scenarios.csv"); assert (d.net_debt<0).all(); assert (d.equity_value>d.fcf*d.ev_fcf_multiple).all()
def test_returns():
 d=pd.read_csv(P/"corrected_valuation_scenarios.csv"); assert ((d.implied_price/d.current_price-1-d.return_pct).abs()<1e-9).all()
def test_dates():
 p=pd.read_csv(P/"latest_prices.csv"); assert p.price_date.eq("2026-11-25").all()
def test_lrn_capex_not_zero():
 d=pd.read_csv(P/"corrected_valuation_scenarios.csv"); l=d[d.ticker=="LRN"]; assert (l.fcf>300e6).all(); assert (l.fcf<504.522e6).all()
def test_all_three():
 d=pd.read_csv(P/"final_decision.csv"); assert set(d.ticker)=={"SFM","LRN","ADUS"}; assert d.decision.eq("WATCH").all()
