import pandas as pd
import pytest

from tools.research.build_treasury_macro_panel import build_treasury_macro_panel


def snapshot(curve_type, retrieved_at, rows):
    return {
        "metadata": {"curve_type": curve_type, "retrieved_at_utc": retrieved_at},
        "rows": rows,
    }


def test_macro_panel_enforces_snapshot_retrieval_time_and_no_future_observation():
    nominal = snapshot("nominal", "2026-10-23T16:00:00Z", [
        {"observation_date": "2026-10-22", "yield_pct": {"2y": 3.5, "3m": 3.0, "10y": 4.0}},
        {"observation_date": "2026-10-26", "yield_pct": {"2y": 3.6, "3m": 3.1, "10y": 4.1}},
    ])
    real = snapshot("real", "2026-10-24T12:00:00Z", [
        {"observation_date": "2026-10-22", "yield_pct": {"10y": 1.8}},
        {"observation_date": "2026-10-26", "yield_pct": {"10y": 1.9}},
    ])
    decisions = pd.DataFrame({"decision_at": [
        "2026-10-23T15:00:00Z",
        "2026-10-24T13:00:00Z",
        "2026-10-27T15:00:00Z",
    ], "ticker": ["AAA", "AAA", "AAA"]})
    panel, report = build_treasury_macro_panel(decisions, nominal, real)
    assert pd.isna(panel.loc[0, "treasury_nominal_10y_pct"])
    assert pd.isna(panel.loc[0, "treasury_real_10y_pct"])
    assert panel.loc[1, "treasury_nominal_10y_pct"] == 4.0
    assert panel.loc[1, "treasury_real_10y_pct"] == 1.8
    assert panel.loc[1, "treasury_breakeven_10y_proxy_bp"] == 220.0
    assert panel.loc[2, "treasury_nominal_10y_pct"] == 4.0
    assert panel.loc[2, "treasury_real_10y_pct"] == 1.8
    assert report["future_or_unavailable_values_filled"] is False
    assert report["historical_first_seen_reconstructed"] is False
    assert report["decision_rows_with_at_least_one_snapshot_available"] == 2


def test_macro_panel_preserves_missing_yields_and_missing_real_curve():
    nominal = snapshot("nominal", "2026-10-20T16:00:00Z", [
        {"observation_date": "2026-10-20", "yield_pct": {"2y": None, "3m": 3.0, "10y": 4.0}},
    ])
    real = snapshot("real", "2026-10-21T16:00:00Z", [
        {"observation_date": "2026-10-20", "yield_pct": {"10y": None}},
    ])
    decisions = pd.DataFrame({"decision_at": ["2026-10-22T15:00:00Z"]})
    panel, _ = build_treasury_macro_panel(decisions, nominal, real)
    assert pd.isna(panel.loc[0, "treasury_nominal_2s10s_bp"])
    assert pd.isna(panel.loc[0, "treasury_breakeven_10y_proxy_bp"])
    assert panel.loc[0, "treasury_nominal_3m10y_bp"] == 100.0


@pytest.mark.parametrize("timestamp", ["", "2026-10-20T16:00:00"])
def test_macro_panel_rejects_naive_decision_timestamp(timestamp):
    nominal = snapshot("nominal", "2026-10-20T16:00:00Z", [])
    real = snapshot("real", "2026-10-20T16:00:00Z", [])
    with pytest.raises(ValueError, match="timezone-aware"):
        build_treasury_macro_panel(pd.DataFrame({"decision_at": [timestamp]}), nominal, real)


def test_macro_panel_rejects_duplicate_dates_and_wrong_curve_type():
    nominal = snapshot("nominal", "2026-10-20T16:00:00Z", [
        {"observation_date": "2026-10-20", "yield_pct": {}},
        {"observation_date": "2026-10-20", "yield_pct": {}},
    ])
    real = snapshot("real", "2026-10-20T16:00:00Z", [])
    with pytest.raises(ValueError, match="duplicate nominal"):
        build_treasury_macro_panel(pd.DataFrame({"decision_at": ["2026-10-21T16:00:00Z"]}), nominal, real)
    nominal = snapshot("real", "2026-10-20T16:00:00Z", [])
    with pytest.raises(ValueError, match="curve_type=nominal"):
        build_treasury_macro_panel(pd.DataFrame({"decision_at": ["2026-10-21T16:00:00Z"]}), nominal, real)
