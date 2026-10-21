# -*- coding: utf-8 -*-
"""Regression tests for Evolve strategy parameter loading/updating (P1-2)."""

import json

import pandas as pd
import pytest

import evolve


def _samples(n=40):
    return pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=n, freq="D").astype(str),
        "score": [70.0] * n,
        "pnl_pct": [1.0] * n,
    })


def _params(core=65):
    return {
        "version": "test",
        "scoring": {
            "core_min_score": core,
            "observation_min_score": 58,
            "ai_weight": 30,
            "quant_weight": 70,
        },
        "exit": {"atr_multiplier": 2.0},
    }


def test_evaluate_score_thresholds_oos_has_no_name_error():
    result = evolve.evaluate_score_thresholds_oos(_samples(40), strategy_params=_params())
    assert isinstance(result, dict)
    assert "eligible" in result
    assert result["baseline_threshold"] == 65.0


def test_evaluate_with_repo_strategy_params_file():
    """The real production parameter file loads and evaluates 40 samples."""
    result = evolve.evaluate_score_thresholds_oos(_samples(40))
    assert isinstance(result, dict)
    assert "eligible" in result
    assert result["baseline_threshold"] == 65.0


def test_insufficient_samples_keep_original_rule():
    result = evolve.evaluate_score_thresholds_oos(_samples(10), strategy_params=_params())
    assert result == {"eligible": False, "reason": "样本不足30笔"}


def test_missing_config_raises_clear_error(tmp_path):
    with pytest.raises(evolve.StrategyParamsError):
        evolve.load_strategy_params(tmp_path / "missing.json")


def test_invalid_config_raises_clear_error(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(evolve.StrategyParamsError):
        evolve.load_strategy_params(path)


def test_apply_parameter_updates_and_persist(tmp_path):
    params = _params(65)
    tv = {"eligible": True, "best": {"threshold": 72}}
    updated, applied = evolve.apply_parameter_updates(params, tv, {"approve": True, "risk_level": "low"})
    assert updated["scoring"]["core_min_score"] == 72
    assert applied == [{
        "name": "core_min_score",
        "old": 65,
        "new": 72,
        "reason": "time-ordered OOS EV >= baseline",
    }]
    assert params["scoring"]["core_min_score"] == 65  # input not mutated

    target = tmp_path / "strategy_params.json"
    evolve.save_strategy_params(updated, target)
    reloaded = json.loads(target.read_text(encoding="utf-8"))
    assert reloaded["scoring"]["core_min_score"] == 72
    assert reloaded["exit"]["atr_multiplier"] == 2.0
    assert reloaded["version"] == "test"


def test_apply_parameter_updates_respects_audit_and_risk():
    params = _params(65)
    tv = {"eligible": True, "best": {"threshold": 72}}
    unchanged, applied = evolve.apply_parameter_updates(params, tv, {"approve": False, "risk_level": "low"})
    assert unchanged["scoring"]["core_min_score"] == 65
    assert applied == []

    unchanged2, applied2 = evolve.apply_parameter_updates(params, tv, {"approve": True, "risk_level": "high"})
    assert unchanged2["scoring"]["core_min_score"] == 65
    assert applied2 == []


def test_save_rejects_invalid_params(tmp_path):
    with pytest.raises(evolve.StrategyParamsError):
        evolve.save_strategy_params({"scoring": {}}, tmp_path / "x.json")
    assert not (tmp_path / "x.json").exists()
