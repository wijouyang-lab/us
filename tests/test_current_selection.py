import pandas as pd
from tools.research.current_live.current_core import latest_session, is_public, quality_or_none, horizon_index, forward_return, snapshot_name, status_for_count

def test_latest_date(): assert str(latest_session(pd.DataFrame({"Date":["2026-11-24","2026-11-25"]})).date())=="2026-11-25"
def test_stale_date_not_latest(): assert str(latest_session(pd.DataFrame({"Date":["2024-12-31"]})).date())!="2026-11-25"
def test_filing_public(): assert is_public("2026-11-04","2026-11-25"); assert not is_public("2026-11-26","2026-11-25"); assert not is_public(None,"2026-11-25")
def test_missing_quality_none(): assert quality_or_none(float("nan")) is None; assert quality_or_none(0.9)==0.9
def test_snapshot_hash_stable(): assert snapshot_name("2026-11-25",{"a":1})==snapshot_name("2026-11-25",{"a":1})
def test_snapshot_hash_diff(): assert snapshot_name("2026-11-25",{"a":1})!=snapshot_name("2026-11-25",{"a":2})
def test_no_candidate_status(): assert status_for_count(0)=="NO_CANDIDATE"; assert status_for_count(2)=="WATCHLIST"
def test_horizon_trading_day_not_calendar():
    dates=pd.bdate_range("2026-11-25",periods=50); assert str(horizon_index(dates,"2026-11-25",5).date())=="2026-12-02"
def test_forward_5d():
    dates=pd.bdate_range("2026-11-25",periods=50); close=[100+i for i in range(50)]; d,r=forward_return(close,dates,"2026-11-25",5); assert d=="2026-12-02" and abs(r-0.05)<1e-12
def test_forward_pending():
    dates=pd.bdate_range("2026-11-25",periods=3); assert forward_return([100,101,102],dates,"2026-11-25",5)==("PENDING",None)
def test_horizon_missing_signal(): assert horizon_index(pd.bdate_range("2026-11-25",periods=50),"2026-11-20",5) is None
def test_no_future_fill(): assert forward_return([100,101,102],pd.bdate_range("2026-11-25",periods=3),"2026-11-25",40)[1] is None
