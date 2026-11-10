# -*- coding: utf-8 -*-
"""Tests for the independent Phase 2.7 accounting audit."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
from volatility_accounting_audit import cost_units, run  # noqa: E402


def test_cost_units_initial_and_zero_turnover():
    assert cost_units(set(), {"A"}, True) == 1.0
    assert cost_units({"A"}, {"A"}, False) == 0.0
    assert cost_units({"A", "B"}, {"A", "C"}, False) == 1.0


def test_short_leg_and_spread_accounting(tmp_path):
    periods = []
    for i in range(3):
        periods.append({
            "signal": f"2021-0{i+1}-01", "entry": f"2021-0{i+1}-02", "exit": f"2021-0{i+1}-03",
            "gross_q1": 0.05, "gross_q5": 0.10, "net_10_q5_q1": 0.05,
            "net_50_q5_q1": 0.05, "q1": ["A"], "q5": ["B"],
        })
    src = tmp_path / "in.json"
    src.write_text(json.dumps({"periods": {"F": {"equal": periods}}}), encoding="utf-8")
    out = tmp_path / "out.json"
    run(str(src), str(out))
    d = json.loads(out.read_text())
    p = d["factors"]["F"]["equal"]["per_period"][0]
    assert p["q1_short_net_10"] == -0.05 - 0.001
    assert p["spread_net_1x_10"] == 0.10 - 0.001 + (-0.05 - 0.001)
    assert p["spread_net_1x_10"] < p["gross_spread"]
    assert p["spread_net_1x_50"] < p["spread_net_1x_10"]
    assert p["spread_net_2x_10"] == p["spread_net_1x_10"] / 2
