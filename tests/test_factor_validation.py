# -*- coding: utf-8 -*-
"""Tests for factor-validation statistics."""

import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
from factor_validation import bh_fdr, newey_west_pvalue  # noqa: E402


def test_bh_fdr_known_order():
    q = bh_fdr([0.01, 0.04, 0.03, 0.20])
    assert q[0] <= q[2] <= q[3]
    assert q[0] == 0.04
    assert q[1] <= 0.2


def test_newey_west_constant_series_is_not_significant():
    mu, se, p = newey_west_pvalue([0.0] * 100)
    assert mu == 0
    assert se == 0
    assert p is None


def test_newey_west_detects_positive_mean():
    rng = np.random.default_rng(1)
    x = 0.02 + rng.normal(0, 0.01, 500)
    mu, se, p = newey_west_pvalue(x)
    assert mu > 0
    assert se > 0
    assert p < 0.01
