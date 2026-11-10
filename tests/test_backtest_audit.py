# -*- coding: utf-8 -*-
"""Fixture checks for the corrected test-scope benchmark audit."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "research"


def test_benchmark_and_factors_use_same_test_dates():
    data = json.loads((ROOT / "restricted_503_backtest_audit_2026-10-29.json").read_text(encoding="utf-8"))
    assert data["test_month_ends"] == 46
    assert data["audit_rows"] == 45
    assert data["benchmark_test"]["n"] == 45
    assert len(data["monthly_audit"]) == 45
    for name in ("Vol60", "ATR_Pct", "Mom12_1", "Mom1", "MA50"):
        assert data["factor_metrics_test"][name]["n"] == 45
    assert data["benchmark_test"]["ann_return"] < data["benchmark_full"]["ann_return"]


def test_full_benchmark_is_not_used_as_test_benchmark():
    data = json.loads((ROOT / "restricted_503_backtest_audit_2026-10-29.json").read_text(encoding="utf-8"))
    assert data["benchmark_full"]["n"] == 120
    assert data["benchmark_test"]["n"] == 45
    assert data["benchmark_full"]["ann_return"] != data["benchmark_test"]["ann_return"]
