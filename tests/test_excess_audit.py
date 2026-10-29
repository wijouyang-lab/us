# -*- coding: utf-8 -*-
"""Fixture checks for paired excess-return audit outputs."""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1] / "docs" / "research"


def test_excess_audit_has_both_processing_modes_and_same_dates():
    data = json.loads((ROOT / "restricted_503_excess_audit_2026-10-29.json").read_text(encoding="utf-8"))
    assert data["test_rows"] == 45
    assert set(data["processing_modes"]) == {"raw", "winsorized"}
    assert len(data["results"]) == 10
    assert data["entry_assumption"].startswith("month-end close")
    for mode in ("raw", "winsorized"):
        rows = [r for r in data["results"] if r["processing"] == mode]
        assert len(rows) == 5
        assert all(r["n"] == 45 for r in rows)


def test_monthly_benchmark_is_identical_across_factors_within_mode():
    df = pd.read_csv(ROOT / "restricted_503_excess_audit_2026-10-29_monthly.csv")
    for mode in ("raw", "winsorized"):
        sub = df[df.processing == mode]
        by_factor = sub.groupby("factor")[["date", "benchmark"]].apply(
            lambda x: list(zip(x.date, x.benchmark))
        )
        first = by_factor.iloc[0]
        assert all(v == first for v in by_factor)
    assert set(df.processing) == {"raw", "winsorized"}
    assert len(df) == 450
