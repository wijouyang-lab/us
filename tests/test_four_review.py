import pandas as pd, hashlib
from pathlib import Path
P=Path("artifacts/four_priority_watch_deep_diligence_v2")
def test_195(): r=pd.read_csv(P/"accounting_195_reconciliation.csv"); assert len(r)==195; assert r.old_status.eq("DATA_UNAVAILABLE").all() and r.new_status.eq("NOT_EVALUATED").all()
def test_ledger(): l=pd.read_csv(P/"candidate_accounting_28000_corrected.csv"); assert len(l)==28000; assert l.status.value_counts().to_dict()=={"EXCLUDED":26463,"CANDIDATE":1342,"NOT_EVALUATED":195}
def test_scen(): d=pd.read_csv(P/"valuation_scenarios.csv"); assert len(d)==12; assert ((d.fcf*d.ev_fcf_multiple-d.net_debt-d.equity_value).abs()<2).all(); assert (d.net_debt<0).all()
def test_price(): p=pd.read_csv(P/"latest_prices.csv"); assert p.price_date.eq("2026-11-25").all()
def test_decisions(): d=pd.read_csv(P/"investment_decisions.csv"); assert len(d)==4 and d.decision.eq("WATCH").all() and (~d.paper).all()
def test_sources(): s=pd.read_csv(P/"source_register.csv"); assert len(s)==4 and s.url.notna().all()
def test_ttm(): f=pd.read_csv(P/"financial_metrics.csv"); assert len(f)==20 and f[f.period=="TTM"].fcf.notna().all()
