import pandas as pd
import pytest

from tools.research.non_atr_validation import apply_turnover_costs, chronological_walk_forward_splits


def test_turnover_costs_charge_entry_and_exit():
    result = apply_turnover_costs(
        pd.Series([0.01, 0.02, -0.01, 0.00]),
        pd.Series([1.0, 1.0, 0.0, 0.0]),
        one_way_cost_bps=10,
    )
    assert result["turnover"].tolist() == [1.0, 0.0, 1.0, 0.0]
    assert result.loc[0, "cost"] == pytest.approx(0.001)
    assert result.loc[2, "cost"] == pytest.approx(0.001)
    assert result.loc[2, "net_return"] < result.loc[2, "gross_return"]


def test_costs_reject_negative_cost_and_short_positions():
    with pytest.raises(ValueError):
        apply_turnover_costs(pd.Series([0.01]), pd.Series([1]), one_way_cost_bps=-1)
    with pytest.raises(ValueError):
        apply_turnover_costs(pd.Series([0.01]), pd.Series([-1]))


def test_walk_forward_is_chronological_and_disjoint():
    dates = pd.date_range("2010-01-01", periods=10, freq="D")
    splits = chronological_walk_forward_splits(dates, min_train_rows=6, test_rows=2)
    assert len(splits) == 2
    assert splits[0]["train_end"] < splits[0]["test_start"]
    assert splits[0]["test_end"] < splits[1]["test_start"]


def test_walk_forward_returns_empty_when_too_short():
    assert chronological_walk_forward_splits(pd.Series(pd.date_range("2020-01-01", periods=5)), min_train_rows=4, test_rows=2) == []
