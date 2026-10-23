from __future__ import annotations

import pandas as pd
import pytest

from tools.research.event_factor_walk_forward import evaluate_walk_forward


def _inputs(tmp_path, n_dates=20):
    signals_path = tmp_path / "signals.csv"
    prices_path = tmp_path / "prices.csv"
    signals = []
    prices = []
    for day in range(n_dates):
        decision_date = pd.Timestamp("2026-01-01", tz="UTC") + pd.Timedelta(days=day)
        decision = decision_date + pd.Timedelta(hours=12)
        for i in range(8):
            ticker = f"T{i}"
            signals.append({
                "decision_at": decision.isoformat(),
                "ticker": ticker,
                "event_score": float(i),
                "coverage_status": "available",
            })
    for day in range(n_dates + 10):
        date = pd.Timestamp("2026-01-01", tz="UTC") + pd.Timedelta(days=day)
        for i in range(8):
            ticker = f"T{i}"
            # Deterministic price history with different ticker-level returns.
            close = 100.0 + i * 2 + day * (i + 1) * 0.2
            prices.append({"date": date.isoformat(), "ticker": ticker, "close": close})
    pd.DataFrame(signals).to_csv(signals_path, index=False)
    pd.DataFrame(prices).to_csv(prices_path, index=False)
    return signals_path, prices_path


def test_walk_forward_is_chronological_purged_and_research_only(tmp_path):
    signals, prices = _inputs(tmp_path)
    result = evaluate_walk_forward(
        str(signals), str(prices), lookback=2, horizon=1,
        cost_bps_per_side=0, quantile=0.25, min_names_per_side=2,
        min_decision_times_per_split=2,
    )
    assert result["status"] == "evaluated"
    assert result["purged_split_counts"]["train"] == result["raw_split_counts"]["train"] - 1
    assert result["purged_split_counts"]["validation"] == result["raw_split_counts"]["validation"] - 1
    assert result["splits"]["train"]["last_decision_at"] < result["splits"]["validation"]["first_decision_at"]
    assert result["splits"]["validation"]["last_decision_at"] < result["splits"]["test"]["first_decision_at"]
    assert result["splits"]["test"]["event_factor"]["decision_dates_tested"] >= 2
    assert result["research_only"] is True
    assert result["production_signal_generated"] is False


def test_walk_forward_fails_closed_when_too_few_dates_remain(tmp_path):
    signals, prices = _inputs(tmp_path, n_dates=5)
    result = evaluate_walk_forward(
        str(signals), str(prices), lookback=2, horizon=2,
        cost_bps_per_side=0, quantile=0.25, min_names_per_side=2,
        min_decision_times_per_split=2,
    )
    assert result["status"] == "insufficient_data"
    assert result["production_signal_generated"] is False


@pytest.mark.parametrize("kwargs", [
    {"train_fraction": 0.8, "validation_fraction": 0.3},
    {"train_fraction": 0},
    {"validation_fraction": 1},
    {"cost_bps_per_side": float("inf")},
])
def test_walk_forward_rejects_invalid_configuration(tmp_path, kwargs):
    signals, prices = _inputs(tmp_path)
    with pytest.raises(ValueError):
        evaluate_walk_forward(str(signals), str(prices), **kwargs)
