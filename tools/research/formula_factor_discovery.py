# -*- coding: utf-8 -*-
"""Research-only mathematical factor candidate generator.

This module generates a small, deterministic family of cross-sectional formula
candidates from columns already present in a point-in-time snapshot. It does
not fit parameters, inspect future returns, execute arbitrary expressions, or
connect candidates to production ranking/trading logic.

Generated values are standardized within each date to reduce scale and
market-wide level effects. Candidate formulas are hypotheses, not evidence of
alpha; validation must be performed separately with chronological out-of-sample
splits, transaction costs, and multiple-testing correction.
"""
from __future__ import annotations

from itertools import combinations
from typing import Iterable

import numpy as np
import pandas as pd


def _cross_sectional_zscore(values: pd.Series, dates: pd.Series) -> pd.Series:
    """Return per-date z-scores; constant/singleton groups become NaN."""
    numeric = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan)
    groups = numeric.groupby(dates, dropna=False)
    means = groups.transform("mean")
    stds = groups.transform(lambda x: x.std(ddof=0))
    safe_std = stds.where(stds > 1e-12)
    return (numeric - means) / safe_std


def generate_formula_candidates(
    frame: pd.DataFrame,
    factor_columns: Iterable[str],
    date_column: str = "Snapshot_Date",
    max_base_factors: int = 12,
) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    """Generate deterministic formula candidates without using a target column.

    Candidate family:
      * z(x)                       -- cross-sectional normalized base factor
      * z(x) - z(y)                -- relative factor balance
      * z(x) * z(y)                -- interaction
      * z(x) / (1 + abs(z(y)))     -- risk/condition-scaled factor

    The caller must pass only information available at the decision timestamp.
    Missing columns are ignored; duplicate column names are removed preserving
    order; the factor list is capped to bound candidate explosion.
    """
    if date_column not in frame.columns:
        raise ValueError(f"missing required date column: {date_column}")

    # Exclude common target/label columns even if accidentally requested.
    # This is a defensive guard; callers must still supply point-in-time features.
    def is_target_column(name: str) -> bool:
        upper = name.upper()
        return (
            upper.startswith("FORWARD_RETURN_")
            or upper.startswith("WIN_")
            or upper in {"TARGET", "LABEL", "Y", "OUTCOME"}
        )

    columns = list(dict.fromkeys(
        c for c in factor_columns
        if c in frame.columns and c != date_column and not is_target_column(c)
    ))[:max_base_factors]
    dates = frame[date_column]
    standardized: dict[str, pd.Series] = {}
    output: dict[str, pd.Series] = {}
    metadata: list[dict[str, str]] = []

    for col in columns:
        z = _cross_sectional_zscore(frame[col], dates)
        standardized[col] = z
        name = f"z__{col}"
        output[name] = z
        metadata.append({"candidate": name, "formula": f"z_cs({col})", "family": "normalized"})

    for left, right in combinations(columns, 2):
        a, b = standardized[left], standardized[right]
        specs = (
            (f"diff__{left}__{right}", a - b, f"z_cs({left}) - z_cs({right})", "difference"),
            (f"prod__{left}__{right}", a * b, f"z_cs({left}) * z_cs({right})", "interaction"),
            (f"scaled__{left}__{right}", a / (1.0 + b.abs()), f"z_cs({left}) / (1 + abs(z_cs({right})))", "scaled"),
        )
        for name, values, formula, family in specs:
            output[name] = values.replace([np.inf, -np.inf], np.nan)
            metadata.append({"candidate": name, "formula": formula, "family": family})

    candidates = pd.DataFrame(output, index=frame.index)
    return candidates, metadata
