from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import pytest
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/"tools"/"research"))
from low_frequency_atr_strategy import clean_frame, chronological_splits, render_report, run_research

def make_frame(n_dates=180,n_tickers=50,direction=1):
    rows=[]
    for di,date in enumerate(pd.bdate_range("2024-01-02",periods=n_dates)):
        for ti in range(n_tickers):
            factor=float(ti)
            ret=direction*factor*0.00002+((ti*7+di)%11-5)*0.00001
            rows.append({"Ticker":f"T{ti:03d}","Scan_Date":date.strftime("%Y-%m-%d"),
                         "ATR_Pct":factor,"Forward_Return_20D":ret})
    return pd.DataFrame(rows)

def test_split_is_chronological_and_purges_twenty_dates():
    dates=list(pd.bdate_range("2024-01-02",periods=180)); s=chronological_splits(dates)
    assert max(s["train"])<min(s["validation"])<max(s["validation"])<min(s["test"])
    assert dates.index(min(s["validation"]))-dates.index(max(s["train"]))-1==20
    assert dates.index(min(s["test"]))-dates.index(max(s["validation"]))-1==20

def test_direction_is_chosen_from_train_and_results_repeat():
    a=run_research(make_frame()); b=run_research(make_frame())
    assert a["direction"]=="HIGH_ATR"
    assert a["segments"]["test"]["n"]>=1
    assert a["verdict"]=="NOT_ENOUGH_TEST_OBSERVATIONS"
    assert a["segments"]["test"]["net_mean_pct"]==pytest.approx(b["segments"]["test"]["net_mean_pct"])

def test_negative_relationship_freezes_low_atr_direction():
    r=run_research(make_frame(direction=-1))
    assert r["direction"]=="LOW_ATR"
    assert r["segments"]["test"]["direction"]=="LOW_ATR"

def test_duplicate_keys_fail_closed():
    d=make_frame(n_dates=120,n_tickers=30); d=pd.concat([d,d.iloc[[0]]],ignore_index=True)
    with pytest.raises(ValueError,match="duplicate Scan_Date/Ticker"): clean_frame(d)

def test_missing_columns_fail_closed():
    with pytest.raises(ValueError,match="missing required columns"):
        clean_frame(pd.DataFrame({"Ticker":["A"],"Scan_Date":["2024-01-01"]}))

def test_report_warns_research_only_and_has_cost_sensitivity():
    report=render_report(run_research(make_frame()))
    assert "研究层，不接生产" in report
    assert "测试期成本敏感性" in report
    assert "不等于证明 alpha" in report
