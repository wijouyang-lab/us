from __future__ import annotations

import pandas as pd

from tools.research.event_factor_family_ablation import evaluate_family_ablations


def test_family_ablation_uses_each_family_coverage_and_paired_baseline(tmp_path):
    signals_path = tmp_path / "signals.csv"
    prices_path = tmp_path / "prices.csv"
    decision = "2026-01-04T12:00:00Z"
    signals = []
    prices = []
    for i in range(8):
        ticker = f"T{i}"
        family_b_available = i < 6
        signals.append({
            "decision_at": decision,
            "ticker": ticker,
            "event_score": i - 3,
            "coverage_status": "available",
            "event_score_family__earnings": i - 3,
            "event_coverage_family__earnings": "available",
            "event_score_family__macro_release": (i % 3) if family_b_available else None,
            "event_coverage_family__macro_release": "available" if family_b_available else "missing",
        })
        prices.extend([
            {"date": "2026-01-01T00:00:00Z", "ticker": ticker, "close": 100},
            {"date": "2026-01-02T00:00:00Z", "ticker": ticker, "close": 100 + i},
            {"date": "2026-01-05T00:00:00Z", "ticker": ticker, "close": 110 if i >= 4 else 90},
            {"date": "2026-01-06T00:00:00Z", "ticker": ticker, "close": 121 if i >= 4 else 81},
        ])
    pd.DataFrame(signals).to_csv(signals_path, index=False)
    pd.DataFrame(prices).to_csv(prices_path, index=False)

    result = evaluate_family_ablations(
        str(signals_path), str(prices_path),
        lookback=2, horizon=1, cost_bps_per_side=0,
        quantile=0.25, min_names_per_side=2,
    )

    assert result["research_only"] is True
    assert result["production_signal_generated"] is False
    assert result["families"]["earnings"]["status"] == "evaluated"
    assert result["families"]["earnings"]["pairing"]["paired_rows"] == 8
    assert result["families"]["macro_release"]["status"] == "evaluated"
    assert result["families"]["macro_release"]["pairing"]["paired_rows"] == 6
    assert result["families"]["earnings"]["price_only_momentum_baseline"]["decision_dates_tested"] == 1


def test_family_ablation_requires_family_score_columns(tmp_path):
    signals_path = tmp_path / "signals.csv"
    prices_path = tmp_path / "prices.csv"
    pd.DataFrame([{"decision_at": "2026-01-04T12:00:00Z", "ticker": "ABC"}]).to_csv(signals_path, index=False)
    pd.DataFrame([{"date": "2026-01-01T00:00:00Z", "ticker": "ABC", "close": 100}]).to_csv(prices_path, index=False)

    try:
        evaluate_family_ablations(str(signals_path), str(prices_path))
    except ValueError as exc:
        assert "event_score_family__" in str(exc)
    else:
        raise AssertionError("expected missing family score columns to be rejected")
