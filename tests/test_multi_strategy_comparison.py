from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import pytest

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/"tools"/"research"))
from multi_strategy_comparison import clean_frame, split_dates, render_report, run_comparison

def make_frame(n_dates=260,n_tickers=50,direction=1):
    rows=[]
    for di,date in enumerate(pd.bdate_range("2023-01-02",periods=n_dates)):
        for ti in range(n_tickers):
            x=ti/max(1,n_tickers-1)
            noise=((di*7+ti*3)%13-6)*0.00001
            rows.append({"Ticker":f"T{ti:03d}","Scan_Date":date.strftime("%Y-%m-%d"),
                "Forward_Return_20D":direction*x*0.01+noise,"ATR_Pct":float(ti),
                "ZScore_20D":float(ti),"Momentum_20D_Pct":float(ti),"MA20_Slope_Pct_5D":float(ti)})
    return pd.DataFrame(rows)

def test_split_purges_twenty_dates():
    dates=list(pd.bdate_range("2023-01-02",periods=260))
    s=split_dates(dates)
    assert dates.index(min(s["validation"]))-dates.index(max(s["train"]))-1==20
    assert dates.index(min(s["test"]))-dates.index(max(s["validation"]))-1==20

def test_comparison_is_deterministic_and_research_only():
    a=run_comparison(make_frame()); b=run_comparison(make_frame())
    assert list(a["results"])==["ATR volatility","Mean reversion","20D momentum","MA slope reversal"]
    for k in a["results"]:
        assert a["results"][k]["direction"]=="HIGH"
        assert a["results"][k]["segments"]["test"]["n"]>=1
        assert a["results"][k]["segments"]["test"]["net_pct"]==pytest.approx(b["results"][k]["segments"]["test"]["net_pct"])
    report=render_report(a)
    assert "Research-only" in report
    assert "Test cost sensitivity" in report
    assert "Do not pick a winner" in report

def test_missing_factor_fails_closed():
    with pytest.raises(ValueError,match="missing required columns"):
        clean_frame(make_frame(n_dates=120).drop(columns=["ZScore_20D"]))

def test_duplicate_rows_fail_closed():
    d=make_frame(n_dates=120)
    with pytest.raises(ValueError,match="duplicate Scan_Date/Ticker"):
        clean_frame(pd.concat([d,d.iloc[[0]]],ignore_index=True))
