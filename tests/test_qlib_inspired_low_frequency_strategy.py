from __future__ import annotations

import numpy as np
import pandas as pd

from tools.research.qlib_inspired_low_frequency_strategy import (
    FEATURES, WEIGHTS, evaluate, load_panel, month_ends, rank_composite,
)


def test_fixed_weights_sum_to_one_and_use_only_declared_features():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-12
    assert set(WEIGHTS) == set(FEATURES)


def test_rank_composite_prefers_consistently_high_ranked_row():
    frame = pd.DataFrame({
        "Mom12_1": [5.0, 1.0, 3.0],
        "Trend100": [5.0, 1.0, 3.0],
        "LowVol60": [5.0, 1.0, 3.0],
        "Reversal5": [5.0, 1.0, 3.0],
        "DollarVolumeTrend": [5.0, 1.0, 3.0],
    })
    score = rank_composite(frame)
    assert score.iloc[0] > score.iloc[2] > score.iloc[1]


def test_month_ends_returns_last_available_session_per_month():
    frame = pd.DataFrame({"Date": pd.to_datetime([
        "2024-01-02", "2024-01-31", "2024-02-01", "2024-02-29"
    ])})
    assert month_ends(frame) == [pd.Timestamp("2024-01-31"), pd.Timestamp("2024-02-29")]


def test_evaluate_does_not_silently_keep_partial_forward_labels():
    # At least MIN_NAMES eligible assets are needed; selected names include a
    # missing forward label, so the month must be rejected rather than shrunk.
    from tools.research.qlib_inspired_low_frequency_strategy import MIN_NAMES
    rows = []
    for i in range(MIN_NAMES):
        row = {"Date": pd.Timestamp("2024-01-31"), "Ticker": f"T{i:03d}",
               "Close": 20.0, "DV20": 10_000_000.0, "Fwd20": 0.01}
        row.update({name: float(i) for name in FEATURES})
        rows.append(row)
    rows[-1]["Fwd20"] = np.nan
    result = evaluate(pd.DataFrame(rows), [pd.Timestamp("2024-01-31")], test_start="2024-01-01")
    assert result["rows"] == []
