import pandas as pd
import pytest

from tools.research.non_atr_validation import apply_turnover_costs


def test_higher_costs_do_not_improve_same_position_path():
    gross = pd.Series([0.0, 0.02, -0.01, 0.03, -0.02, 0.01])
    position = pd.Series([0.0, 1.0, 1.0, 0.0, 1.0, 1.0])
    zero = apply_turnover_costs(gross, position, one_way_cost_bps=0.0)
    five = apply_turnover_costs(gross, position, one_way_cost_bps=5.0)
    twenty = apply_turnover_costs(gross, position, one_way_cost_bps=20.0)

    assert zero["turnover"].tolist() == five["turnover"].tolist()
    assert five["turnover"].tolist() == twenty["turnover"].tolist()
    assert (five["net_return"] <= zero["net_return"] + 1e-12).all()
    assert (twenty["net_return"] <= five["net_return"] + 1e-12).all()
    assert five.loc[five["turnover"] > 0, "cost"].gt(0).all()


def test_cost_sensitivity_rejects_negative_cost():
    with pytest.raises(ValueError, match="cannot be negative"):
        apply_turnover_costs(pd.Series([0.01]), pd.Series([1.0]), one_way_cost_bps=-1)
