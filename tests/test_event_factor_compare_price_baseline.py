from __future__ import annotations

import pandas as pd

from tools.research.event_factor_compare_price_baseline import build_paired_signals, compare


def _inputs(tmp_path):
    signals_path = tmp_path / "signals.csv"
    prices_path = tmp_path / "prices.csv"
    decision = "2026-01-04T12:00:00Z"
    signals = []
    prices = []
    for i in range(8):
        ticker = f"T{i}"
        signals.append({
            "decision_at": decision,
            "ticker": ticker,
            "event_score": i,
            "coverage_status": "available",
        })
        prices.extend([
            {"date": "2026-01-01T00:00:00Z", "ticker": ticker, "close": 100},
            {"date": "2026-01-02T00:00:00Z", "ticker": ticker, "close": 100 + i},
            {"date": "2026-01-05T00:00:00Z", "ticker": ticker, "close": 110 if i >= 4 else 90},
            {"date": "2026-01-06T00:00:00Z", "ticker": ticker, "close": 121 if i >= 4 else 81},
        ])
    pd.DataFrame(signals).to_csv(signals_path, index=False)
    pd.DataFrame(prices).to_csv(prices_path, index=False)
    return signals_path, prices_path


def test_paired_baseline_uses_only_prices_before_decision_date(tmp_path):
    signals, prices = _inputs(tmp_path)
    paired, report = build_paired_signals(str(signals), str(prices), lookback=2)
    assert len(paired) == 8
    assert report["paired_universe"] is True
    assert paired.sort_values("ticker")["momentum_score"].is_monotonic_increasing


def test_event_factor_and_price_baseline_share_paired_universe(tmp_path):
    signals, prices = _inputs(tmp_path)
    result = compare(
        str(signals),
        str(prices),
        lookback=2,
        horizon=1,
        cost_bps_per_side=0,
        quantile=0.25,
        min_names_per_side=2,
    )
    assert result["status"] == "evaluated"
    assert result["pairing"]["paired_rows"] == 8
    assert result["event_factor"]["decision_dates_tested"] == 1
    assert result["price_only_momentum_baseline"]["decision_dates_tested"] == 1
    assert result["production_signal_generated"] is False



def test_paired_universe_excludes_non_finite_scores_and_prices(tmp_path):
    signals_path = tmp_path / "signals.csv"
    prices_path = tmp_path / "prices.csv"
    signals = []
    prices = []
    for i in range(8):
        ticker = f"T{i}"
        signals.append({
            "decision_at": "2026-01-04T12:00:00Z",
            "ticker": ticker,
            "event_score": "inf" if i == 7 else i,
            "coverage_status": "available",
        })
        prices.extend([
            {"date": "2026-01-01T00:00:00Z", "ticker": ticker, "close": 100},
            {"date": "2026-01-02T00:00:00Z", "ticker": ticker, "close": "inf" if i == 6 else 100 + i},
            {"date": "2026-01-05T00:00:00Z", "ticker": ticker, "close": 110 + i},
            {"date": "2026-01-06T00:00:00Z", "ticker": ticker, "close": 111 + i},
        ])
    pd.DataFrame(signals).to_csv(signals_path, index=False)
    pd.DataFrame(prices).to_csv(prices_path, index=False)

    paired, report = build_paired_signals(str(signals_path), str(prices_path), lookback=2)
    assert report["paired_universe"] is True
    assert "T6" not in set(paired["ticker"])
    assert "T7" not in set(paired["ticker"])
    assert len(paired) == 6



def test_paired_comparison_reports_hac_uncertainty(tmp_path):
    from tools.research.event_factor_compare_price_baseline import _newey_west_mean_interval

    result = _newey_west_mean_interval([0.01, 0.02, 0.03, 0.04], max_lag=1)
    assert result["status"] == "estimated"
    assert result["observations"] == 4
    assert result["max_lag"] == 1
    assert result["mean_difference_pct"] == 2.5
    assert result["ci95_lower_pct"] < result["mean_difference_pct"] < result["ci95_upper_pct"]
    assert "does not remove selection bias" in result["interpretation_warning"]


def test_hac_uncertainty_stays_unavailable_for_too_few_dates():
    from tools.research.event_factor_compare_price_baseline import _newey_west_mean_interval

    result = _newey_west_mean_interval([0.01, 0.02], max_lag=19)
    assert result["status"] == "insufficient_data"
    assert result["ci95_lower_pct"] is None
    assert result["ci95_upper_pct"] is None
