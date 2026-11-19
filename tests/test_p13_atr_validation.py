import numpy as np
import pandas as pd
from scipy import stats

from tools.research.p13_atr_validation import atr_frame, bh, hac_t


def test_atr_uses_only_prior_and_current_bars():
    n = 25
    g = pd.DataFrame({"high": np.arange(n) + 2.0, "low": np.arange(n) + 0.0, "close": np.arange(n) + 1.0})
    a = atr_frame(g)
    assert np.isnan(a.iloc[0])
    g2 = g.copy(); g2.loc[n - 1, "high"] = 100
    # ATR at t=n-2 must not change when a later bar changes.
    assert atr_frame(g2).iloc[n - 2] == a.iloc[n - 2]


def test_hac_and_bh_finite():
    x = np.linspace(-.01, .02, 50)
    assert np.isfinite(hac_t(x))
    q = bh([.01, .04, .03])
    assert np.all(q >= 0) and np.all(q <= 1)


def test_member_day_coverage_denominator_is_not_global_history():
    # Guard the coverage definition: 5Y member coverage must be based on dates,
    # not the 1996-2026 snapshot count.
    d = pd.read_json("data/research/p13/p13_data_readiness.json", typ="series")
    assert d["membership_days"] < 3000
    assert 0 <= d["member_day_coverage"] <= 1
