import numpy as np
import pandas as pd

from tools.research.p12_5_3_macro_equity_alpha import bh, fwd, z_dev


def test_z_dev_uses_only_prior_events():
    s = pd.Series([1.0 + i * 0.1 for i in range(40)] + [10.0])
    z = z_dev(s)
    assert z.iloc[:36].isna().all()
    assert np.isfinite(z.iloc[36])
    before = z.iloc[36]
    s2 = s.copy(); s2.iloc[40] = 999
    assert z_dev(s2).iloc[36] == before


def test_fwd_missing_future_is_none():
    idx = pd.bdate_range("2020-01-01", periods=5)
    s = pd.Series(range(5), index=idx, dtype=float)
    spy = pd.Series(range(5), index=idx, dtype=float)
    assert fwd(s, spy, idx, idx[0], 20) is None


def test_bh_monotone():
    q = bh([.01, .04, .03, .2])
    assert np.all(q >= 0) and np.all(q <= 1)
    assert q.min() <= q.max()
def test_fwd_requires_same_spy_dates():
    idx = pd.bdate_range("2020-01-01", periods=6)
    s = pd.Series([1, 2, 3, 4, 5, 6], index=idx, dtype=float)
    spy = pd.Series([1, 1, 1, 1, 1, 1], index=idx, dtype=float)
    assert fwd(s, spy, idx, idx[0], 5) is not None
    assert fwd(s, spy, idx, idx[0], 6) is None
    s2 = s.drop(idx[5])
    assert fwd(s2, spy, idx, idx[0], 5) is None
