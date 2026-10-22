from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import pytest

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/"tools"/"research"))
from multi_strategy_comparison import clean_frame, split_dates, render_report, run_comparison, daily_rows, daily_rows_both_directions, metrics

def make_frame(n_dates=260,n_tickers=50,direction=1):
    rows=[]
    for di,date in enumerate(pd.bdate_range("2023-01-02",periods=n_dates)):
        for ti in range(n_tickers):
            x=ti/max(1,n_tickers-1)
            noise=((di*7+ti*3)%13-6)*0.00001
            rows.append({"Ticker":f"T{ti:03d}","Scan_Date":date.strftime("%Y-%m-%d"),
                "Forward_Return_20D":direction*x*0.01+noise,"ATR_Pct":float(ti),
                "Realized_Volatility_20D_Pct":float(ti),"ZScore_20D":float(ti),
                "Momentum_20D_Pct":float(ti),"Momentum_60D_Pct":float(ti),
                "RSI":float(ti),"MA20_Slope_Pct_5D":float(ti)})
    return pd.DataFrame(rows)

def test_split_purges_twenty_dates():
    dates=list(pd.bdate_range("2023-01-02",periods=260))
    s=split_dates(dates)
    assert dates.index(min(s["validation"]))-dates.index(max(s["train"]))-1==20
    assert dates.index(min(s["test"]))-dates.index(max(s["validation"]))-1==20

def test_comparison_is_deterministic_and_research_only():
    a=run_comparison(make_frame()); b=run_comparison(make_frame())
    assert list(a["results"])==["ATR volatility","Realized volatility","Mean reversion","RSI signal","20D momentum","60D momentum","MA slope reversal"]
    for k in a["results"]:
        assert a["results"][k]["direction"]=="HIGH"
        assert a["results"][k]["segments"]["test"]["n"]>=1
        assert a["results"][k]["segments"]["test"]["net_pct"]==pytest.approx(b["results"][k]["segments"]["test"]["net_pct"])
    report=render_report(a)
    assert "Research-only" in report
    assert "Test cost sensitivity" in report
    assert "Do not pick a winner" in report

def test_vectorized_portfolio_rows_match_reference():
    d=clean_frame(make_frame(n_dates=120))
    dates=list(pd.unique(d.Scan_Date))
    high,low=daily_rows_both_directions(d,dates,"ATR_Pct")
    for actual,reference in (
        (high,daily_rows(d,dates,"ATR_Pct",1)),
        (low,daily_rows(d,dates,"ATR_Pct",-1)),
    ):
        assert len(actual)==len(reference)
        for got,want in zip(actual,reference):
            assert got["date"]==want["date"]
            assert got["tickers"]==want["tickers"]
            assert got["gross"]==pytest.approx(want["gross"],abs=1e-12)
            assert got["benchmark"]==pytest.approx(want["benchmark"],abs=1e-12)


def test_vectorized_rows_exclude_missing_factor_names_before_count_and_benchmark():
    d = clean_frame(make_frame(n_dates=120, n_tickers=40))
    date = min(d.Scan_Date)
    d.loc[(d.Scan_Date == date) & (d.Ticker.isin([f"T{i:03d}" for i in range(15)])), "ATR_Pct"] = float("nan")
    dates = list(pd.unique(d.Scan_Date))
    high, low = daily_rows_both_directions(d, dates, "ATR_Pct")
    for actual, reference in (
        (high, daily_rows(d, dates, "ATR_Pct", 1)),
        (low, daily_rows(d, dates, "ATR_Pct", -1)),
    ):
        assert len(actual) == len(reference)
        assert all(got["date"] == want["date"] for got, want in zip(actual, reference))
        for got, want in zip(actual, reference):
            assert got["tickers"] == want["tickers"]
            assert got["gross"] == pytest.approx(want["gross"], abs=1e-12)
            assert got["benchmark"] == pytest.approx(want["benchmark"], abs=1e-12)
    # Only 25 factor-valid names remain on this date, below MIN_NAMES=30.
    assert date not in {row["date"] for row in high}
    assert date not in {row["date"] for row in low}

def test_missing_factor_fails_closed():
    with pytest.raises(ValueError,match="missing required columns"):
        clean_frame(make_frame(n_dates=120).drop(columns=["ZScore_20D"]))

def test_duplicate_rows_fail_closed():
    d=make_frame(n_dates=120)
    with pytest.raises(ValueError,match="duplicate Scan_Date/Ticker"):
        clean_frame(pd.concat([d,d.iloc[[0]]],ignore_index=True))


def test_drawdown_includes_initial_capital_baseline():
    rows = [
        {"tickers": frozenset({"A"}), "gross": -0.10, "benchmark": 0.0},
        {"tickers": frozenset({"A"}), "gross": 0.05, "benchmark": 0.0},
    ]
    result = metrics(rows, cost_bps=0)
    # First period drops equity from 1.0 to 0.9; the following rebound
    # remains below the initial peak, so the maximum drawdown is -10%.
    assert result["drawdown_pct"] == pytest.approx(-10.0)
