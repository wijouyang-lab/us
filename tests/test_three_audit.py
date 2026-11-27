import pandas as pd, math
from pathlib import Path
P=Path("artifacts/three_candidate_cashflow_valuation_audit_v1")
def test_files(): assert all((P/f).exists() for f in ["executive_summary.md","entity_and_consolidation_audit.csv","quarterly_financials.csv","fcf_reconciliation.csv","sbc_dilution_audit.csv","customer_concentration_audit.csv","normalized_fcf.csv","valuation_scenarios.csv","valuation_comparison.csv","risk_register.csv","catalyst_and_invalidation.csv","source_register.csv","final_decisions.csv","validation_report.md"])
def test_immr(): d=pd.read_csv(P/"valuation_scenarios.csv"); assert d[d.ticker=="IMMR"].price.isna().all()
def test_phr(): d=pd.read_csv(P/"fcf_reconciliation.csv"); r=d[d.ticker=="PHR"].iloc[0]; assert abs(float(r.reported_fcf)-float(r.sbc)-float(r.adjusted_fcf))<2
def test_oprx(): d=pd.read_csv(P/"fcf_reconciliation.csv"); r=d[d.ticker=="OPRX"].iloc[0]; assert abs(float(r.reported_fcf)-float(r.sbc)-float(r.adjusted_fcf))<2
def test_formula(): d=pd.read_csv(P/"valuation_scenarios.csv").dropna(subset=["price"]); assert ((d.fcf*d.multiple-d.net_debt-d.equity).abs()<2).all()
def test_price(): d=pd.read_csv(P/"valuation_comparison.csv"); assert d.price_date.eq("2026-11-25").all()
def test_decisions(): d=pd.read_csv(P/"final_decisions.csv"); assert len(d)==3 and (~d.paper).all(); assert d[d.ticker=="IMMR"].decision.iloc[0]=="INSUFFICIENT_DATA"
