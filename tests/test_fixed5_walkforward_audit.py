# -*- coding: utf-8 -*-
"""Fixture checks for fixed-five annual OOS audit."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "research"


def test_annual_oos_has_all_years_and_factors():
    d = json.loads((ROOT / "fixed5_walkforward_2026-10-29.json").read_text(encoding="utf-8"))
    assert d["test_years"] == [2023, 2024, 2025, 2026]
    assert len(d["annual"]) == 20
    by = {(r["year"], r["factor"]): r for r in d["annual"]}
    assert by[(2023, "Mom12_1")]["n"] == 12
    assert by[(2026, "Mom12_1")]["n"] == 9
    assert d["entry_assumption"].startswith("month-end close")


def test_annual_oos_is_not_a_new_factor_search():
    d = json.loads((ROOT / "fixed5_walkforward_2026-10-29.json").read_text(encoding="utf-8"))
    assert "no selection" in d["note"]
    assert len({r["factor"] for r in d["annual"]}) == 5
