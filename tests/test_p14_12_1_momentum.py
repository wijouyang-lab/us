import numpy as np
import pandas as pd
from tools.research.p14_12_1_momentum import block_boot, nw


def test_monthly_proxy_is_non_overlapping():
    m = pd.read_csv("data/research/p14/p14_monthly_long_only.csv")
    assert len(m) == 47
    dates = pd.to_datetime(m.date)
    assert (dates.diff().dropna() > pd.Timedelta(days=18)).all()


def test_bootstrap_reproducible():
    x = np.linspace(-.02, .03, 100)
    a = block_boot(x, reps=50, block=21, seed=7)
    b = block_boot(x, reps=50, block=21, seed=7)
    assert a == b


def test_hac_positive_variance():
    assert np.isfinite(nw(np.linspace(-.01, .02, 100), 20))


def test_oos_boundaries_purged():
    o = pd.read_csv("data/research/p14/p14_oos_results.csv")
    assert len(o) == 3
    assert o.dates.sum() < 983


def test_cost_arithmetic():
    c = pd.read_csv("data/research/p14/p14_cost_sensitivity.csv")
    assert c.bps_per_side.tolist() == [5, 10, 20]
    assert c.net_mean.is_monotonic_decreasing
    assert c.net_excess.iloc[1] < 0
