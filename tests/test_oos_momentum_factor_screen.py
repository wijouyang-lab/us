from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "research"))
from oos_momentum_factor_screen import (
    chronological_splits,
    evaluate_factor_segment,
    newey_west_mean_tstat,
)


def test_chronological_splits_are_ordered_disjoint_and_purged():
    dates = list(pd.bdate_range("2024-01-01", periods=100))
    splits = chronological_splits(dates, purge_dates=5)
    train, validation, test = splits["train"], splits["validation"], splits["test"]
    assert max(train) < min(validation) < max(validation) < min(test)
    assert len(train) == 55
    assert len(validation) == 15
    assert len(test) == 20
    date_idx = {d: i for i, d in enumerate(dates)}
    assert date_idx[min(validation)] - date_idx[max(train)] - 1 == 5
    assert date_idx[min(test)] - date_idx[max(validation)] - 1 == 5


def test_factor_segment_finds_positive_predeclared_momentum_spread():
    rows = []
    dates = list(pd.bdate_range("2025-01-01", periods=50))
    for day_i, date in enumerate(dates):
        for ticker_i in range(50):
            signal = float(ticker_i)
            idio = ((ticker_i * (day_i + 3)) % 13 - 6) * 0.00015
            row = {
                "Scan_Date": date,
                "Ticker": f"T{ticker_i:03d}",
                "Momentum_20D_Pct": signal,
            }
            for h in (5, 10, 20):
                row[f"Forward_Return_{h}D"] = signal * 0.0007 + idio + (day_i % 5) * 0.00005
            rows.append(row)
    frame = pd.DataFrame(rows)
    result = evaluate_factor_segment(frame, dates, min_names_per_date=30)
    for horizon in (5, 10, 20):
        assert result[horizon]["valid_dates"] == 50
        assert result[horizon]["valid_rows"] == 2500
        assert result[horizon]["top_bottom_spread"] > 0
        assert result[horizon]["mean_daily_ic"] > 0
        assert result[horizon]["spread_hac_t"] is not None


def test_hac_t_statistic_is_finite_and_deterministic():
    values = [0.01, 0.02, -0.003, 0.015, 0.007, 0.022, 0.001, 0.018]
    a = newey_west_mean_tstat(values, 3)
    b = newey_west_mean_tstat(values, 3)
    assert a is not None and np.isfinite(a) and a > 0
    assert a == b
    assert newey_west_mean_tstat([1.0, 1.0, 1.0], 1) is None


if __name__ == "__main__":
    tests = [
        test_chronological_splits_are_ordered_disjoint_and_purged,
        test_factor_segment_finds_positive_predeclared_momentum_spread,
        test_hac_t_statistic_is_finite_and_deterministic,
    ]
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
    print(f"Result: {len(tests)}/{len(tests)} passed")
