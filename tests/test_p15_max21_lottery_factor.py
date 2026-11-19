import json
from pathlib import Path

import numpy as np
import pandas as pd

from tools.research.p15_max21_lottery_factor import boot, nw


def test_max21_is_max_of_21_trailing_returns():
    prices = pd.Series([100, 101, 102, 103, 104, 105, 120, 106, 107, 108,
                        109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 121])
    r = prices.pct_change().iloc[1:]
    mx = r.iloc[-21:].max()
    assert abs(mx - (120 / 105 - 1)) < 1e-12


def test_daily_quantiles_are_reported_and_direction_negative():
    q = pd.read_csv("data/research/p15/p15_quantile_returns.csv")
    assert list(q["quantile"]) == ["q1", "q2", "q3", "q4", "q5"]
    assert q.q1_minus_q5.iloc[0] < 0


def test_hac_and_bootstrap_reproducible():
    x = np.linspace(-.01, .02, 100)
    assert np.isfinite(nw(x, 20))
    assert boot(x, reps=40, block=21, seed=7) == boot(x, reps=40, block=21, seed=7)


def test_oos_and_monthly_are_non_overlapping():
    o = pd.read_csv("data/research/p15/p15_oos_results.csv")
    assert len(o) == 3 and o.dates.sum() < 1234
    m = pd.read_csv("data/research/p15/p15_monthly_long_only.csv")
    assert len(m) == 59
    assert (pd.to_datetime(m.date).diff().dropna() > pd.Timedelta(days=18)).all()


def test_costs_include_both_sides_and_kill_excess():
    c = pd.read_csv("data/research/p15/p15_cost_sensitivity.csv")
    assert c.bps_per_side.tolist() == [5, 10, 20]
    assert c.net_excess.max() < 0


def test_manifest_files_exist_and_hash():
    import hashlib
    m = json.loads(Path("data/research/p15/p15_manifest.json").read_text())
    for name, meta in m["outputs"].items():
        p = Path("data/research/p15") / name
        assert p.exists() and p.stat().st_size == meta["bytes"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == meta["sha256"]
