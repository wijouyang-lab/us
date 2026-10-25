# -*- coding: utf-8 -*-
"""Regression tests for research-only mathematical factor generation."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.research.formula_factor_discovery import generate_formula_candidates


def test_formula_candidates_are_deterministic_and_cross_sectional():
    frame = pd.DataFrame({
        "Snapshot_Date": ["2026-01-01"] * 5 + ["2026-01-02"] * 5,
        "Momentum_20D_Pct": list(range(5)) + list(range(100, 105)),
        "ATR_Pct": [1, 2, 3, 4, 5] * 2,
        "Forward_Return_5D": [999] * 10,  # must never be used by generator
    })
    a, meta_a = generate_formula_candidates(
        frame, ["Momentum_20D_Pct", "ATR_Pct", "Forward_Return_5D"]
    )
    b, meta_b = generate_formula_candidates(
        frame, ["Momentum_20D_Pct", "ATR_Pct", "Forward_Return_5D"]
    )
    pd.testing.assert_frame_equal(a, b)
    assert meta_a == meta_b
    assert "Forward_Return_5D" not in a.columns
    assert np.isclose(a.loc[0, "z__Momentum_20D_Pct"], a.loc[5, "z__Momentum_20D_Pct"])
    assert len(meta_a) == 2 + 3


def test_formula_candidates_ignore_missing_columns_and_bound_factor_count():
    frame = pd.DataFrame({
        "Snapshot_Date": ["d1"] * 4,
        "x": [1, 2, 3, 4],
        "y": [4, 3, 2, 1],
        "z": [1, 1, 2, 2],
    })
    result, meta = generate_formula_candidates(
        frame, ["x", "missing", "y", "z"], max_base_factors=2
    )
    assert "z__x" in result
    assert "z__y" in result
    assert "z__z" not in result
    assert len(meta) == 2 + 3


def test_formula_candidates_constant_group_is_missing_not_zero():
    frame = pd.DataFrame({
        "Snapshot_Date": ["d1"] * 4,
        "constant": [5, 5, 5, 5],
    })
    result, _ = generate_formula_candidates(frame, ["constant"])
    assert result["z__constant"].isna().all()


def test_formula_candidates_require_date_column():
    with pytest.raises(ValueError, match="date column"):
        generate_formula_candidates(pd.DataFrame({"x": [1, 2]}), ["x"])
