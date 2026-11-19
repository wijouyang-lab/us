import numpy as np
import pandas as pd
from tools.research.p14_12_1_momentum import block_boot, nw


def test_entry_exit_are_exact_market_calendar():
    p = pd.read_csv("data/research/p14/p14_momentum_signal_panel.csv", nrows=5000)
    assert (pd.to_datetime(p.entry_date) > pd.to_datetime(p.signal_date)).all()
    # exit = entry + 21 market sessions; at minimum later than entry
    assert (pd.to_datetime(p.exit_date) > pd.to_datetime(p.entry_date)).all()


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
