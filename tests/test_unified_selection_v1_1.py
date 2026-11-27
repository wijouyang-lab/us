import pandas as pd, json, hashlib
from pathlib import Path
P=Path("data/research/unified_selection/unified_selection_v1_1.csv")
def test_rows_unique(): d=pd.read_csv(P); assert len(d)==5600 and d.ticker.nunique()==5600
def test_groups(): d=pd.read_csv(P); assert d.comparable_group.nunique()==30; assert (d.groupby("comparable_group").group_eligible_n.first()>=20).sum()==6; assert d.research_rank.notna().sum()==491
def test_special_industry(): d=pd.read_csv(P); assert int(d.special_industry.sum())==959; assert set(d[d.special_industry].industry).issubset({"BANKS","INSURANCE","REIT","OTHER_FINANCIALS"})
def test_blocked_not_ranked(): d=pd.read_csv(P); assert d[d.research_group=="BLOCKED"].research_rank.isna().all()
def test_gate_blocks_small_eligible(): d=pd.read_csv(P); bad=d[d.group_eligible_n<20]; assert bad.research_rank.isna().all() and (bad.composite_status=="NOT_COMPARABLE").all()
def test_gate_allows_20plus(): d=pd.read_csv(P); good=d[d.group_eligible_n>=20]; assert (good.research_rank.notna()==good.composite_ready).all()
def test_tier_a_conditions(): d=pd.read_csv(P); a=d[d.research_group=="TIER_A"]; assert (a.group_eligible_n>=20).all() and (a.dimension_coverage==4).all() and (a.group_rank<=5).all()
def test_tier_sum(): d=pd.read_csv(P); assert d.research_group.value_counts().sum()==5600
def test_composite_not_comparable_marked(): d=pd.read_csv(P); assert set(d.composite_status).issubset({"NOT_COMPARABLE","GROUP_COMPARABLE_DISPLAY_ONLY"}); assert d.composite_legacy_not_comparable.all()
def test_missing_not_zero(): d=pd.read_csv(P); assert d.pb.isna().sum()>0 and d.composite_score.isna().sum()>0
def test_pe_unavailable(): d=pd.read_csv(P); assert d.pe.isna().all() and (d.pe_reason=="UNAVAILABLE_NOT_IN_SOURCE_RANKING").all()
def test_traceability(): d=pd.read_csv(P); assert (d.fundamental_source!="").sum()>0; assert (d.fiscal_period!="").sum()>0; assert (d.filing_date!="").sum()>0
def test_forward_unavailable(): d=pd.read_csv(P); assert (d.forward_eps=="UNAVAILABLE").all()
def test_page_json_hash():
 p=Path("dashboard/data/unified_selection_v1_1.json"); assert hashlib.sha256(p.read_bytes()).hexdigest()==Path("dashboard/data/unified_selection_v1_1.sha256").read_text().strip(); assert len(json.loads(p.read_text())["rows"])==5600
def test_unknown_traceability_clean():
 d=pd.read_csv(P)
 for c in ["fundamental_source","fiscal_period","filing_date","accession"]:
  assert d[c].notna().all()
  assert (~d[c].astype(str).str.lower().eq("nan")).all()
  assert (~d[c].astype(str).str.strip().eq("")).all()
 assert (d.fundamental_source=="UNKNOWN").sum()==303

def test_page_shows_fiscal_period():
 p=Path("terminal/unified.html").read_text(encoding="utf-8")
 assert 'fiscal period <b>${r.fiscal_period||"UNKNOWN"}</b>' in p

def test_page_hides_non_comparable_score():
 p=Path("terminal/unified.html").read_text(encoding="utf-8")
 assert 'r.composite_status==="GROUP_COMPARABLE_DISPLAY_ONLY"' in p
 assert '<th>Peer score (display only)</th>' in p
 assert '<option value="composite_score">' not in p
