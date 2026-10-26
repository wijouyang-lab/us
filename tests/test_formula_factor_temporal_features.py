"""Tests for point-in-time temporal factor construction."""
import numpy as np
import pandas as pd
import pytest

from tools.research.run_formula_factor_validation import _add_temporal_feature_changes


def _history_frame() -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    dates = pd.date_range("2026-01-05", periods=22, freq="B")
    rows = []
    for ticker, available_sessions in (("AAA", range(22)), ("BBB", range(1, 22))):
        for session in available_sessions:
            rows.append({
                "Snapshot_Date": dates[session],
                "Ticker": ticker,
                "Momentum_20D_Pct": float(session),
                "RSI": float(session * 2),
                "ATR_Pct": float(100 + session),
            })
    return pd.DataFrame(rows), dates


def test_temporal_changes_use_exact_prior_snapshot_and_not_future_rows() -> None:
    frame, dates = _history_frame()
    result = _add_temporal_feature_changes(frame)
    row = result.loc[
        (result["Ticker"] == "AAA") & (result["Snapshot_Date"] == dates[20])
    ].iloc[0]

    assert row["Momentum_20D_Acceleration_20_Snapshots"] == pytest.approx(20.0)
    assert row["RSI_Change_5_Snapshots"] == pytest.approx(10.0)
    assert row["ATR_Pct_Change_20_Snapshots"] == pytest.approx(20.0)

    # BBB has no row at the exact 20-snapshot lag. The helper must not
    # substitute the next available ticker row.
    missing_lag = result.loc[
        (result["Ticker"] == "BBB") & (result["Snapshot_Date"] == dates[20])
    ].iloc[0]
    assert np.isnan(missing_lag["Momentum_20D_Acceleration_20_Snapshots"])
    assert np.isnan(missing_lag["ATR_Pct_Change_20_Snapshots"])

    changed_future = frame.copy()
    future = (changed_future["Ticker"] == "AAA") & (changed_future["Snapshot_Date"] == dates[21])
    changed_future.loc[future, ["Momentum_20D_Pct", "RSI", "ATR_Pct"]] = [5000, 6000, 7000]
    future_result = _add_temporal_feature_changes(changed_future)
    future_row = future_result.loc[
        (future_result["Ticker"] == "AAA") & (future_result["Snapshot_Date"] == dates[20])
    ].iloc[0]
    assert future_row["Momentum_20D_Acceleration_20_Snapshots"] == pytest.approx(
        row["Momentum_20D_Acceleration_20_Snapshots"]
    )
    assert future_row["RSI_Change_5_Snapshots"] == pytest.approx(
        row["RSI_Change_5_Snapshots"]
    )


def test_temporal_changes_reject_duplicate_ticker_snapshot_rows() -> None:
    frame, _ = _history_frame()
    duplicate = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="unique ticker/date"):
        _add_temporal_feature_changes(duplicate)
