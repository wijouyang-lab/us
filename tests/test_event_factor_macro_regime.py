import pandas as pd
import pytest

from tools.research.event_factor_macro_regime import evaluate_macro_regimes


def test_macro_regime_evaluation_excludes_unavailable_and_stale_rows(tmp_path):
    signals = pd.DataFrame({
        "decision_at": [
            "2026-10-20T15:00:00Z",
            "2026-10-21T15:00:00Z",
            "2026-10-22T15:00:00Z",
        ],
        "ticker": ["AAA", "AAA", "AAA"],
        "event_score": [0.8, 0.7, 0.6],
        "coverage_status": ["available"] * 3,
    })
    macro = pd.DataFrame({
        "decision_at": signals["decision_at"],
        "treasury_nominal_2s10s_bp": [-20.0, 15.0, -5.0],
        "treasury_nominal_available_at_utc": ["2026-10-20T14:00:00Z"] * 3,
        "treasury_nominal_age_days": [0, 1, 20],
        "treasury_nominal_available": [True, True, True],
    })
    signal_path, macro_path = tmp_path / "signals.csv", tmp_path / "macro.csv"
    signals.to_csv(signal_path, index=False)
    macro.to_csv(macro_path, index=False)
    prices_path = tmp_path / "prices.csv"
    pd.DataFrame({"date": ["2026-10-16", "2026-10-19"], "ticker": ["AAA", "AAA"], "close": [10.0, 10.2]}).to_csv(prices_path, index=False)
    result = evaluate_macro_regimes(
        str(signal_path), str(prices_path), str(macro_path),
        max_feature_age_days=5,
    )
    assert result["input_signal_rows"] == 3
    assert result["rows_after_pit_and_staleness_filter"] == 2
    assert result["excluded_rows"] == 1
    assert result["regimes"]["inverted_2s10s"]["status"] == "insufficient_data"
    assert result["regimes"]["non_inverted_2s10s"]["status"] == "insufficient_data"
    assert result["alpha_established"] is False


def test_macro_regime_evaluation_rejects_disagreeing_duplicate_macro_rows(tmp_path):
    signals = pd.DataFrame({
        "decision_at": ["2026-10-20T15:00:00Z"],
        "ticker": ["AAA"],
        "event_score": [0.8],
        "coverage_status": ["available"],
    })
    macro = pd.DataFrame({
        "decision_at": ["2026-10-20T15:00:00Z", "2026-10-20T15:00:00Z"],
        "treasury_nominal_2s10s_bp": [-20.0, 10.0],
        "treasury_nominal_available_at_utc": ["2026-10-20T14:00:00Z"] * 2,
        "treasury_nominal_age_days": [0, 0],
        "treasury_nominal_available": [True, True],
    })
    signal_path, macro_path = tmp_path / "signals.csv", tmp_path / "macro.csv"
    signals.to_csv(signal_path, index=False)
    macro.to_csv(macro_path, index=False)
    prices_path = tmp_path / "prices.csv"
    pd.DataFrame({"date": ["2026-10-16"], "ticker": ["AAA"], "close": [10.0]}).to_csv(prices_path, index=False)
    with pytest.raises(ValueError, match="differs across rows"):
        evaluate_macro_regimes(str(signal_path), str(prices_path), str(macro_path))


def test_macro_regime_evaluation_requires_expected_columns(tmp_path):
    signals = pd.DataFrame({
        "decision_at": ["2026-10-20T15:00:00Z"],
        "ticker": ["AAA"], "event_score": [0.8], "coverage_status": ["available"],
    })
    macro = pd.DataFrame({"decision_at": ["2026-10-20T15:00:00Z"]})
    signal_path, macro_path = tmp_path / "signals.csv", tmp_path / "macro.csv"
    signals.to_csv(signal_path, index=False)
    macro.to_csv(macro_path, index=False)
    prices_path = tmp_path / "prices.csv"
    pd.DataFrame({"date": ["2026-10-16"], "ticker": ["AAA"], "close": [10.0]}).to_csv(prices_path, index=False)
    with pytest.raises(ValueError, match="macro panel requires"):
        evaluate_macro_regimes(str(signal_path), str(prices_path), str(macro_path))
