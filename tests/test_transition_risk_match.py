from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tools.research.transition_risk_match import (
    DataValidationError,
    analyze,
    load_input,
    match_volatility,
    simulate_monthly_passive,
)

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/research/transition_risk_match/transition_risk_match_input.csv"


def test_pinned_input_has_complete_aligned_history():
    frame = load_input(INPUT)
    assert len(frame) == 4888
    assert frame.date.iloc[0].date().isoformat() == "2007-05-30"
    assert frame.date.iloc[-1].date().isoformat() == "2026-10-30"
    assert frame.date.is_monotonic_increasing
    assert not frame.date.duplicated().any()


def test_risk_match_weights_and_volatility_are_reproducible():
    frame = load_input(INPUT)
    results, _ = analyze(frame)
    expected = {
        "w25_c10_all_legs": 0.1040714997,
        "w50_c10_all_legs": 0.1992858706,
        "w100_c10_all_legs": 0.3740037767,
    }
    for name, weight in expected.items():
        item = results["comparisons"][name]
        assert item["passive_diagnostics"]["qqq_weight"] == pytest.approx(weight, abs=2e-7)
        assert item["passive"]["volatility"] == pytest.approx(
            item["strategy"]["volatility"], abs=1e-8
        )
        assert item["passive_diagnostics"]["order_legs"] == 466
        assert item["passive_diagnostics"]["rebalance_sessions"] == 233


def test_passive_control_outperforms_transition_on_cagr_at_all_three_risk_levels():
    frame = load_input(INPUT)
    results, _ = analyze(frame)
    for item in results["comparisons"].values():
        assert item["passive"]["cagr"] > item["strategy"]["cagr"]


def test_monthly_rebalance_charges_each_executed_leg():
    frame = load_input(INPUT)
    nav, details = simulate_monthly_passive(frame, 0.20, 10.0)
    assert len(nav) == len(frame)
    assert details["order_legs"] == details["buy_legs"] + details["sell_legs"]
    assert details["order_legs"] > 0
    assert details["total_cost_usd"] == pytest.approx(
        details["total_traded_notional_usd"] * 0.001
    )


def test_invalid_price_or_duplicate_date_fails_closed(tmp_path):
    frame = load_input(INPUT).head(8).copy()
    frame.loc[3, "qqq_adj_open"] = 0.0
    path = tmp_path / "bad_price.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(DataValidationError):
        load_input(path)

    frame = load_input(INPUT).head(8).copy()
    frame.loc[3, "date"] = frame.loc[2, "date"]
    path = tmp_path / "duplicate_date.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(DataValidationError):
        load_input(path)


def test_target_volatility_outside_passive_range_is_rejected():
    frame = load_input(INPUT)
    with pytest.raises(DataValidationError):
        match_volatility(frame, 0.50)
