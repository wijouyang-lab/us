import pandas as pd, json, hashlib
from pathlib import Path
P=Path("data/research/unified_selection/unified_selection_v1_1.csv")
def test_rows_unique(): d=pd.read_csv(P); assert len(d)==5600 and d.ticker.nunique()==5600
def test_groups(): d=pd.read_csv(P); assert d.comparable_group.nunique()>=20; assert (d.groupby("comparable_group").size()>=20).sum()==23
def test_special_industry(): d=pd.read_csv(P); assert int(d.special_industry.sum())==959; assert set(d[d.special_industry].industry).issubset({"BANKS","INSURANCE","REIT","OTHER_FINANCIALS"})
def test_blocked_not_ranked(): d=pd.read_csv(P); assert d[d.research_group=="BLOCKED"].research_rank.isna().all()
def test_composite_not_comparable_marked(): d=pd.read_csv(P); assert set(d.composite_status).issubset({"NOT_COMPARABLE","GROUP_COMPARABLE_DISPLAY_ONLY"}); assert d.composite_legacy_not_comparable.all()
def test_missing_not_zero(): d=pd.read_csv(P); assert d.pb.isna().sum()>0 and d.composite_score.isna().sum()>0
def test_pe_unavailable(): d=pd.read_csv(P); assert d.pe.isna().all() and (d.pe_reason=="UNAVAILABLE_NOT_IN_SOURCE_RANKING").all()
def test_traceability(): d=pd.read_csv(P); assert (d.fundamental_source!="").sum()>0; assert (d.fiscal_period!="").sum()>0; assert (d.filing_date!="").sum()>0
def test_forward_unavailable(): d=pd.read_csv(P); assert (d.forward_eps=="UNAVAILABLE").all()
def test_page_json_hash():
 p=Path("dashboard/data/unified_selection_v1_1.json"); assert hashlib.sha256(p.read_bytes()).hexdigest()==Path("dashboard/data/unified_selection_v1_1.sha256").read_text().strip(); assert len(json.loads(p.read_text())["rows"])==5600
