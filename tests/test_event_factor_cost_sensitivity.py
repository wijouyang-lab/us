from __future__ import annotations

import pandas as pd
import pytest

from tools.research.event_factor_cost_sensitivity import evaluate_grid, _float_grid, _int_grid


def test_cost_sensitivity_grid_reports_all_declared_combinations(tmp_path):
    signal_path = tmp_path / "signals.csv"
    price_path = tmp_path / "prices.csv"
    decision = "2026-01-02T12:00:00Z"
    signals = []
    prices = []
    for i in range(8):
        ticker = f"T{i}"
        signals.append({
            "decision_at": decision,
            "ticker": ticker,
            "event_score": i,
            "coverage_status": "available",
        })
        prices.extend([
            {"date": "2026-01-03T00:00:00Z", "ticker": ticker, "close": 110 if i >= 4 else 90},
            {"date": "2026-01-04T00:00:00Z", "ticker": ticker, "close": 121 if i >= 4 else 81},
        ])
    pd.DataFrame(signals).to_csv(signal_path, index=False)
    pd.DataFrame(prices).to_csv(price_path, index=False)

    result = evaluate_grid(
        str(signal_path),
        str(price_path),
        horizons=[1, 1],
        costs_bps=[0, 10],
        quantile=0.25,
        min_names_per_side=2,
    )

    assert result["status"] == "evaluated"
    assert result["grid_rows"] == 2
    assert result["evaluated_grid_rows"] == 2
    assert result["production_signal_generated"] is False
    zero_cost, higher_cost = result["results"]
    assert zero_cost["cost_bps_per_side"] == 0
    assert higher_cost["cost_bps_per_side"] == 10
    assert zero_cost["mean_net_return_pct"] > higher_cost["mean_net_return_pct"]


def test_sensitivity_grid_parsers_reject_invalid_values():
    assert _int_grid("20,5,20", "horizons") == [5, 20]
    assert _float_grid("10,0,5", "costs") == [0.0, 5.0, 10.0]
    with pytest.raises(ValueError):
        _int_grid("0,5", "horizons")
    with pytest.raises(ValueError):
        _float_grid("-1,5", "costs")
