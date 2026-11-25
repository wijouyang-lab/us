import pandas as pd
from tools.investment_research.fs2.composite import pct_rank
def test_pct_rank_missing():
 s=pd.Series([1,None,3]); r=pct_rank(s); assert r.isna().sum()==1
def test_tiers():
 d=pd.read_csv("data/research/fs2/composite_candidates_v1.csv"); assert set(d.composite_tier)=={"BLOCKED","WATCH","TIER_1","TIER_2"}
def test_tier1_multi():
 d=pd.read_csv("data/research/fs2/composite_candidates_v1.csv"); assert (d[d.composite_tier=="TIER_1"].style_count>=2).all()
def test_eligible_not_blocked():
 d=pd.read_csv("data/research/fs2/composite_candidates_v1.csv"); e=d[d.tradability_status=="ELIGIBLE_FOR_RESEARCH"]; assert (e.composite_tier!="BLOCKED").all()
def test_style_counts():
 d=pd.read_csv("data/research/fs2/composite_candidates_v1.csv"); assert int(d.value_top20.sum())==170; assert int(d.quality_top20.sum())==463
def test_missing_not_zero():
 d=pd.read_csv("data/research/fs2/composite_candidates_v1.csv"); assert d.value_pct.isna().sum()>0
def test_ca_blocked():
 d=pd.read_csv("data/research/fs2/composite_candidates_v1.csv"); c=d[d.tradability_reason=="CORPORATE_ACTION_REVIEW"]; assert len(c)>0 and (c.composite_tier=="BLOCKED").all()
def test_shortlist_subset():
 d=pd.read_csv("data/research/fs2/composite_candidates_v1.csv"); s=pd.read_csv("data/research/fs2/composite_shortlist_v1.csv"); assert set(s.ticker).issubset(set(d.ticker))
