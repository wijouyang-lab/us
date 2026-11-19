import numpy as np
import pandas as pd

from tools.research.p12_5_fomc_rate_beta import beta, bh, fwd_excess


def test_beta_recovers_coefficients_and_ignores_future():
    rng = np.random.default_rng(7)
    idx = pd.bdate_range("2020-01-01", periods=400)
    spy = pd.Series(1 + rng.normal(0, .01, len(idx)), index=idx).cumprod()
    tlt = pd.Series(1 + rng.normal(0, .01, len(idx)), index=idx).cumprod()
    stock = pd.Series(1 + .5 * spy.pct_change().fillna(0) - .25 * tlt.pct_change().fillna(0), index=idx).cumprod()
    b = beta(stock, spy, tlt, idx[-30], 252, 180)
    assert b is not None
    assert abs(b[0] - .5) < .15 and abs(b[1] + .25) < .15
    before = beta(stock, spy, tlt, idx[-30], 252, 180)
    stock2 = stock.copy()
    stock2.loc[idx[-29]:] *= 2
    after = beta(stock2, spy, tlt, idx[-30], 252, 180)
    assert before == after


def test_forward_excess_uses_future_only():
    idx = pd.bdate_range("2020-01-01", periods=30)
    spy = pd.Series(np.linspace(100, 110, 30), index=idx)
    stock = pd.Series(np.linspace(50, 60, 30), index=idx)
    assert fwd_excess(stock, spy, idx[5], 5) is not None


def test_bh_is_monotone_and_bounded():
    q = bh(np.array([.01, .04, .03, .2]))
    assert np.all(q >= 0) and np.all(q <= 1)
    assert q[0] <= q[1]
