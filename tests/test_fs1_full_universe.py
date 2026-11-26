import pandas as pd
def test_identity_validation():
 d=pd.read_csv("data/universe/price_liquidity/universe_identity_v1.csv",dtype=str); assert len(d)==5615; assert (d.ticker_status=="VALID").sum()==5600
def test_full_status():
 d=pd.read_csv("data/universe/price_liquidity/download_status_v1.csv",dtype=str); assert len(d)==5501; assert (d.status=="SUCCESS").sum()==5044
def test_common_coverage_90():
 d=pd.read_csv("data/universe/price_liquidity/download_status_v1.csv",dtype=str); c=d[d.security_type=="COMMON"]; assert c.has20.astype(str).str.lower().eq("true").mean()>=0.90
def test_total_20d():
 d=pd.read_csv("data/universe/price_liquidity/download_status_v1.csv",dtype=str); assert d.has20.astype(str).str.lower().eq("true").sum()==5021
def test_top101_150():
 d=pd.read_csv("data/universe/price_liquidity/top101_150_audit_v1.csv",dtype=str); assert len(d)==150; assert (d.final_status=="ELIGIBLE").sum()==132
def test_corporate_actions_blocked():
 d=pd.read_csv("data/universe/price_liquidity/corporate_action_audit_v1.csv",dtype=str); assert len(d)==470; assert d.corporate_action_status.eq("CORPORATE_ACTION_REVIEW").all()
