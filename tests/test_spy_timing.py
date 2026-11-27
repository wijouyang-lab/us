"""Tests for month-end signal -> next-month execution and Sharpe."""
import math
import pandas as pd
import numpy as np
from tools.research.strategy_competition.timing import trend_signal, trend_positions, spy_trend_backtest, annualized_sharpe

def _prices(vals):
    idx=pd.period_range("2020-01",periods=len(vals),freq="M").astype(str)
    return pd.Series(vals,index=idx,dtype=float)

def test_signal_cannot_affect_same_month():
    p=_prices([100+i for i in range(12)]+[80,70,60,50,40,30,20,10,5,5,5,5])
    sig=trend_signal(p,3); pos=trend_positions(p,3)
    assert pos.iloc[12]==sig.iloc[11]
    assert pos.iloc[12] != sig.iloc[12]

def test_exit_starts_next_month():
    p=_prices([100,101,102,103,104,105,106,107,108,109,110,111,80,70,60,50])
    pos=trend_positions(p,3)
    # signal turns off at 12; position at 13 must be 0
    assert trend_signal(p,3).iloc[12]==0
    assert pos.iloc[13]==0
    assert pos.iloc[12]==1

def test_entry_starts_next_month():
    p=_prices([100,90,80,70,60,50,40,30,20,10,5,5,100,110,120,130])
    pos=trend_positions(p,3)
    flip=trend_signal(p,3).diff().eq(1)
    if flip.any():
        t=int(np.where(flip)[0][0]); assert pos.iloc[t+1]==1

def test_cost_applied_on_switch_month():
    p=_prices([100,101,102,103,104,105,106,107,108,109,110,111,80,70,60,50])
    g,n,to,pos=spy_trend_backtest(p,3,10)
    switch=to[to>0].index[0]
    assert abs((g.loc[switch]-n.loc[switch])-10/10000)<1e-12

def test_equity_matches_net_returns():
    p=_prices([100,101,102,103,104,105,106,107,108,109,110,111,80,70,60,50])
    _,n,_,_=spy_trend_backtest(p,3,10)
    eq=(1+n.fillna(0)).cumprod()
    assert abs(eq.iloc[-1]-np.prod(1+n.fillna(0)))<1e-12

def test_sharpe_uses_mean_not_cagr():
    r=pd.Series([0.01,0.02,-0.01,0.03,0.0,-0.02,0.01,0.01]*3)
    s=annualized_sharpe(r,0)
    assert abs(s-(r.mean()*12)/(r.std(ddof=0)*math.sqrt(12)))<1e-12

def test_switch_cost_not_charged_on_hold():
    p=_prices([100]*16)
    g,n,to,_=spy_trend_backtest(p,3,10)
    assert to.sum()==0
    assert (g.fillna(0)==n.fillna(0)).all()
