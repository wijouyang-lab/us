import pandas as pd, json, hashlib
from pathlib import Path
P=Path("artifacts/priority_candidates_investment_review_v1")
def test_ledger(): l=pd.read_csv(P/"candidate_accounting_28000.csv"); assert len(l)==28000; assert l.status.isin(["CANDIDATE","EXCLUDED","DATA_UNAVAILABLE"]).all(); assert set(l.style)=={"VALUE","QUALITY","GARP","TREND","TURNAROUND"}
def test_quality(): q=pd.read_csv(P/"data_quality_reconciliation.csv"); assert q.candidate_rows.sum()==1342
def test_historical(): d=pd.read_csv(P/"investment_decisions.csv"); assert d[d.ticker=="CRMD"].decision.iloc[0]=="ELIMINATE"
def test_priority(): d=pd.read_csv(P/"investment_decisions.csv"); assert len(d[d.decision=="PRIORITY_WATCH"])==4
def test_no_paper(): d=pd.read_csv(P/"investment_decisions.csv"); assert (d.decision!="PAPER_CANDIDATE").all()
def test_unique(): d=pd.read_csv(P/"investment_decisions.csv"); assert len(d)==39 and d.ticker.nunique()==39
def test_sources(): s=pd.read_csv(P/"source_register.csv"); assert len(s)==39 and s.url.notna().all()
def test_ttm(): f=pd.read_csv(P/"financial_metrics.csv"); assert len(f)==39 and "ttm_method" in f
def test_snapshot():
 p=Path("dashboard/data/multi_style_candidates_v1.json"); assert hashlib.sha256(p.read_bytes()).hexdigest()==Path("dashboard/data/multi_style_candidates_v1.sha256").read_text().strip()
