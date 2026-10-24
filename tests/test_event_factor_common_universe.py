from __future__ import annotations

import pandas as pd
import pytest

from tools.research.event_factor_common_universe import build_common_universe


def test_common_universe_requires_available_finite_scores_for_every_family():
    signals = pd.DataFrame([
        {
            "decision_at": "2026-01-01T12:00:00Z", "ticker": "AAA",
            "event_score_family__earnings": 0.8, "event_coverage_family__earnings": "available",
            "event_score_family__macro_release": -0.2, "event_coverage_family__macro_release": "available",
        },
        {
            "decision_at": "2026-01-01T12:00:00Z", "ticker": "BBB",
            "event_score_family__earnings": 0.4, "event_coverage_family__earnings": "available",
            "event_score_family__macro_release": None, "event_coverage_family__macro_release": "missing",
        },
        {
            "decision_at": "2026-01-01T12:00:00Z", "ticker": "CCC",
            "event_score_family__earnings": float("inf"), "event_coverage_family__earnings": "available",
            "event_score_family__macro_release": 0.1, "event_coverage_family__macro_release": "available",
        },
    ])

    common, report = build_common_universe(signals)

    assert common["ticker"].tolist() == ["AAA"]
    assert report["input_rows"] == 3
    assert report["common_universe_rows"] == 1
    assert report["excluded_rows"] == 2
    assert report["missing_values_imputed"] is False
    assert report["research_only"] is True


def test_common_universe_rejects_missing_family_coverage_column():
    signals = pd.DataFrame([{
        "decision_at": "2026-01-01T12:00:00Z", "ticker": "AAA",
        "event_score_family__earnings": 0.8,
    }])
    with pytest.raises(ValueError, match="missing coverage column"):
        build_common_universe(signals)
