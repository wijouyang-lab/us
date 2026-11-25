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
import pandas as pd
from pathlib import Path
def test_matrix_no_blocked_tier():
 d=pd.read_csv("data/research/fs2/composite_candidates_v1.csv"); assert len(d[(d.tradability_status=="BLOCKED")&(d.composite_tier.isin(["TIER_1","TIER_2"]))])==0
def test_insufficient_not_tier():
 d=pd.read_csv("data/research/fs2/composite_candidates_v1.csv"); assert len(d[(d.tradability_status=="INSUFFICIENT_DATA")&(d.composite_tier.isin(["TIER_1","TIER_2"]))])==0
def test_unique_ticker():
 d=pd.read_csv("data/research/fs2/composite_candidates_v1.csv"); assert d.ticker.duplicated().sum()==0
def test_page_and_data():
 assert Path("terminal/candidates.html").exists(); assert Path("dashboard/data/fs2_candidates_v1.json").exists()
def test_ca_count_469():
 d=pd.read_csv("data/research/fs2/composite_candidates_v1.csv"); assert len(d[d.tradability_reason=="CORPORATE_ACTION_REVIEW"])==469
from tools.investment_research.fs2.composite import decide_tradability, decide_tier
def test_identity_block(): assert decide_tradability("ETF","1",None,True,True,True,True)[0]=="BLOCKED"
def test_ca_block(): assert decide_tradability("COMMON","1","CORPORATE_ACTION_REVIEW",True,True,True,True)[0]=="BLOCKED"
def test_ca_missing_not_pass(): assert decide_tradability("COMMON","1","CORPORATE_ACTION_REVIEW",True,True,True,True)[1]=="CORPORATE_ACTION_REVIEW"
def test_missing_price_insufficient(): assert decide_tradability("COMMON","1","OK",False,True,True,True)[0]=="INSUFFICIENT_DATA"
def test_adr_watch(): assert decide_tradability("ADR","1","OK",True,True,True,True)[0]=="WATCH"
def test_low_adv_block(): assert decide_tradability("COMMON","1","OK",True,False,True,True)[1]=="LIQUIDITY_BELOW_RESEARCH_FLOOR"
def test_stale_watch(): assert decide_tradability("COMMON","1","OK",True,True,False,True)[0]=="WATCH"
def test_60d_watch(): assert decide_tradability("COMMON","1","OK",True,True,True,False)[0]=="WATCH"
def test_eligible(): assert decide_tradability("COMMON","1","OK",True,True,True,True)[0]=="ELIGIBLE_FOR_RESEARCH"
def test_tier_block(): assert decide_tier("BLOCKED",4)=="BLOCKED"
def test_tier_insuff(): assert decide_tier("INSUFFICIENT_DATA",4)=="WATCH"
def test_tier1(): assert decide_tier("ELIGIBLE_FOR_RESEARCH",2)=="TIER_1"
def test_tier2(): assert decide_tier("ELIGIBLE_FOR_RESEARCH",1)=="TIER_2"
from tools.investment_research.fs2.composite import decide_tradability, decide_tier
from tools.investment_research.fs2.publish_snapshot import validate
import json
def test_etf_priority_over_ca(): assert decide_tradability("ETF","1","CORPORATE_ACTION_REVIEW",True,True,True,True)[1]=="IDENTITY_NOT_COMMON_OR_ADR"
def test_adr_low_adv_watch(): assert decide_tradability("ADR","1","OK",True,False,True,True)[0]=="WATCH"
def test_ca_priority_over_price(): assert decide_tradability("COMMON","1","CORPORATE_ACTION_REVIEW",False,True,True,True)[1]=="CORPORATE_ACTION_REVIEW"
def test_stale_and_60_watch(): assert decide_tradability("COMMON","1","OK",True,True,False,False)[0]=="WATCH"
def test_style_zero_watch(): assert decide_tier("ELIGIBLE_FOR_RESEARCH",0)=="WATCH"
def test_tier1_requires_two(): assert decide_tier("ELIGIBLE_FOR_RESEARCH",2)=="TIER_1"
def test_tier2_requires_one(): assert decide_tier("ELIGIBLE_FOR_RESEARCH",1)=="TIER_2"
def test_valid_snapshot_validate():
 d=json.load(open("dashboard/data/fs2_candidates_v1.json")); assert validate(d)==5600
