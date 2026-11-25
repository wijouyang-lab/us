import pandas as pd
from pathlib import Path
P=Path("data/universe/price_liquidity")
def test_identity_counts():
 d=pd.read_csv(P/"universe_identity_v1.csv",dtype=str); assert len(d)==5615; assert d.security_type.value_counts()["COMMON"]==5187; assert d.security_type.value_counts()["ADR"]==315
def test_top100_union():
 s=pd.read_csv(P/"top100_status_v1.csv"); assert len(s)==285 and s.ticker.nunique()==285
def test_top100_all_20d():
 a=pd.read_csv(P/"liquidity_metrics_v1.csv"); assert len(a)==285 and (a.valid_days>=20).all()
def test_corporate_actions_blocked():
 a=pd.read_csv(P/"liquidity_metrics_v1.csv"); c=pd.read_csv(P/"top100_coverage_audit_v1.csv"); assert a.corporate_action_status.ne("OK").sum()==22; assert (c[c.ticker.isin(a[a.corporate_action_status.ne("OK")].ticker)].final_status=="BLOCKED").all()
def test_adv_positive():
 a=pd.read_csv(P/"liquidity_metrics_v1.csv"); assert (a.adv20_usd.dropna()>0).all()
def test_coverage_statuses():
 c=pd.read_csv(P/"top100_coverage_audit_v1.csv"); assert c.final_status.value_counts().to_dict()=={"ELIGIBLE":198,"BLOCKED":61,"WATCH":26}
