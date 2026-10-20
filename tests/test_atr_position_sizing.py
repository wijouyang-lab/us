# -*- coding: utf-8 -*-
"""ATR report metric contract tests; no market-data or network access."""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.research.atr_position_sizing import ROUND_TRIP_COST_BPS, stats


def test_stats_label_units_match_computation():
    # Non-overlap sample is values at 0, 20, 40. Mean is a single-holding-period return.
    values = [0.01] * 41
    values[0] = -0.10
    values[20] = 0.05
    values[40] = 0.03
    result = stats(values, h=20)
    selected = [-0.10, 0.05, 0.03]
    expected_total = math.prod(1 + x for x in selected) - 1
    expected_mean = sum(selected) / len(selected) * 100
    assert result["n"] == 3
    assert math.isclose(result["total"], expected_total * 100, abs_tol=1e-9)
    assert math.isclose(result["mean_period"], expected_mean, abs_tol=1e-9)


def test_first_period_loss_counts_in_max_drawdown():
    values = [0.01] * 41
    values[0] = -0.10
    values[20] = 0.05
    values[40] = 0.03
    result = stats(values, h=20)
    assert math.isclose(result["mdd"], -10.0, abs_tol=1e-9), result["mdd"]


def test_round_trip_cost_is_nonnegative_and_reasonable_default():
    assert ROUND_TRIP_COST_BPS >= 0
    assert math.isclose(ROUND_TRIP_COST_BPS, 11.0, abs_tol=1e-9)


def main():
    tests = [
        test_stats_label_units_match_computation,
        test_first_period_loss_counts_in_max_drawdown,
        test_round_trip_cost_is_nonnegative_and_reasonable_default,
    ]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"[PASS] {test.__name__}")
        except Exception as exc:
            failures += 1
            print(f"[FAIL] {test.__name__}: {exc}")
    print(f"\n结果：通过 {len(tests) - failures}/{len(tests)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
