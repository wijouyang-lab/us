import pandas as pd, math
from pathlib import Path
P=Path("artifacts/three_candidate_cashflow_valuation_audit_v1")

def test_period_revenue():
 r=pd.read_csv(P/"period_reconciliation.csv"); x=r[(r.ticker=="PHR")&(r.item=="Revenue")].iloc[0]
 assert abs(x.fy+x.ytd-x.prior_ytd-x.ttm)<1e-6 and abs(x.ttm-507.793)<1e-3

def test_period_ocf():
 r=pd.read_csv(P/"period_reconciliation.csv"); x=r[(r.ticker=="PHR")&(r.item=="OCF")].iloc[0]
 assert abs(x.fy+x.ytd-x.prior_ytd-x.ttm)<1e-6 and abs(x.ttm-91.379)<1e-3

def test_period_fcf():
 r=pd.read_csv(P/"period_reconciliation.csv"); x=r[(r.ticker=="PHR")&(r.item=="Reported FCF")].iloc[0]
 assert abs(x.fy+x.ytd-x.prior_ytd-x.ttm)<1e-6 and abs(x.ttm-67.522)<1e-3

def test_no_mixed_period():
 r=pd.read_csv(P/"period_reconciliation.csv"); p=r[r.ticker=="PHR"]
 assert set(p.formula)=={"FY+current YTD-prior YTD"}

def test_unit():
 r=pd.read_csv(P/"period_reconciliation.csv"); assert r.unit.eq("USD millions").all()

def test_ocf_capex_fcf_separate():
 q=pd.read_csv(P/"quarterly_financials.csv"); assert {"ocf","total_capex","fcf"}.issubset(q.columns); assert q[q.ticker=="PHR"].fcf.iloc[-1] != q[q.ticker=="PHR"].ocf.iloc[-1]

def test_fcf_formula():
 q=pd.read_csv(P/"quarterly_financials.csv"); p=q[q.ticker.isin(["PHR","OPRX"])].dropna(subset=["fcf"])
 assert ((p.ocf-p.total_capex-p.fcf).abs()<0.002).all()

def test_sbc_total_component():
 s=pd.read_csv(P/"quarterly_sbc_history.csv"); p=s[s.period=="TTM"]
 assert all(abs(x.total_sbc-(x.expense_sbc+x.capitalized_sbc))<0.002 for _,x in p.iterrows())

def test_cap_sbc_no_double():
 f=pd.read_csv(P/"fcf_reconciliation.csv"); p=f[f.ticker=="PHR"].iloc[0]
 assert abs((p.reported_fcf-p.total_sbc)-p.fcf_total_sbc)<0.002
 assert abs(p.total_sbc-(p.expense_sbc+1.214))<0.002

def test_accelerated_sbc():
 s=pd.read_csv(P/"quarterly_sbc_history.csv"); x=s[(s.ticker=="OPRX")&(s.period=="9M 2026")].iloc[0]
 assert abs(x.accelerated_sbc-0.588)<1e-9

def test_immr_entities():
 e=pd.read_csv(P/"fcf_ownership_reconciliation.csv"); p=e[e.entity=="Immersion parent"].iloc[0]; b=e[e.entity=="BNED"].iloc[0]
 assert abs(p.revenue_fy2026-15.924)<1e-6 and abs(b.revenue_fy2026-1714.770)<1e-6

def test_immr_nci():
 v=pd.read_csv(P/"valuation_comparison.csv"); x=v[v.ticker=="IMMR"].iloc[0]
 assert "NCI" in x.reason and pd.isna(x.normalized_fcf)

def test_immr_no_base():
 s=pd.read_csv(P/"valuation_scenarios.csv"); assert s[s.ticker=="IMMR"].price.isna().all()

def test_price_date():
 v=pd.read_csv(P/"valuation_comparison.csv"); assert v.price_date.eq("2026-11-25").all()

def test_shares():
 s=pd.read_csv(P/"valuation_scenarios.csv").dropna(subset=["price"])
 assert abs((s.equity/s.shares-s.price).max())<1e-6

def test_missing_not_zero():
 f=pd.read_csv(P/"financial_metrics.csv"); x=f[(f.ticker=="IMMR")&(f.period=="FY2026 parent")].iloc[0]
 assert pd.isna(x.fcf) and pd.isna(x.ocf)

def test_sources_trace():
 s=pd.read_csv(P/"source_register.csv"); assert len(s)>=6 and s.url.notna().all(); assert {"10-K","10-Q"}.issubset(set(s.form))

def test_paper_gate():
 d=pd.read_csv(P/"final_decisions.csv"); assert len(d)==3 and (~d.paper).all(); assert (d.decision!="PAPER_CANDIDATE").all()
