"""Transaction-cost and chronological walk-forward helpers for research baselines."""
from __future__ import annotations

import pandas as pd


def apply_turnover_costs(
    strategy_returns: pd.Series,
    positions: pd.Series,
    *,
    one_way_cost_bps: float = 5.0,
) -> pd.DataFrame:
    """Deduct proportional costs on position changes; inputs are aligned daily series.

    Cost is charged on absolute position turnover, including opening/closing exposure.
    The strategy return is assumed to be earned by the position held over that day.
    """
    if one_way_cost_bps < 0:
        raise ValueError("one_way_cost_bps cannot be negative")
    frame = pd.DataFrame({
        "gross_return": pd.to_numeric(strategy_returns, errors="coerce"),
        "position": pd.to_numeric(positions, errors="coerce"),
    }).dropna()
    if frame.empty:
        return pd.DataFrame(columns=["gross_return", "position", "turnover", "cost", "net_return"])
    if not frame["position"].between(0, 1).all():
        raise ValueError("positions must be between 0 and 1 for this long-only helper")
    previous = frame["position"].shift(1).fillna(0.0)
    frame["turnover"] = (frame["position"] - previous).abs()
    frame["cost"] = frame["turnover"] * (one_way_cost_bps / 10000.0)
    frame["net_return"] = (1.0 + frame["gross_return"]) * (1.0 - frame["cost"]) - 1.0
    return frame


def chronological_walk_forward_splits(
    dates: pd.Series,
    *,
    min_train_rows: int = 756,
    test_rows: int = 252,
    step_rows: int | None = None,
) -> list[dict]:
    """Build expanding-window train/test splits without shuffling or overlap leakage."""
    if min_train_rows < 2 or test_rows < 1:
        raise ValueError("min_train_rows must be >= 2 and test_rows must be >= 1")
    step = test_rows if step_rows is None else step_rows
    if step < 1:
        raise ValueError("step_rows must be >= 1")
    parsed = pd.to_datetime(pd.Series(dates), errors="coerce").dropna().sort_values().drop_duplicates().reset_index(drop=True)
    if len(parsed) < min_train_rows + test_rows:
        return []
    splits = []
    train_end = min_train_rows
    while train_end + test_rows <= len(parsed):
        test_start = train_end
        test_end = test_start + test_rows
        splits.append({
            "train_start": parsed.iloc[0].date().isoformat(),
            "train_end": parsed.iloc[train_end - 1].date().isoformat(),
            "test_start": parsed.iloc[test_start].date().isoformat(),
            "test_end": parsed.iloc[test_end - 1].date().isoformat(),
            "train_rows": train_end,
            "test_rows": test_rows,
        })
        train_end += step
    return splits
