from __future__ import annotations

import json

import pandas as pd

from tools.research.build_pit_event_signal_panel import build_panel
from tools.research.pit_event_archive import merge_event_archive


def test_panel_builds_asof_scores_and_preserves_missingness(tmp_path):
    decision = "2026-01-10T15:00:00Z"
    raw_events = [
        {
            "event_id": "abc-good",
            "event_type": "earnings",
            "tickers": ["ABC"],
            "sectors": [],
            "availability_status": "available",
            "published_at_utc": "2026-01-10T13:00:00Z",
            "first_seen_at_utc": "2026-01-10T13:01:00Z",
            "direction_score": 1,
            "impact_score": 1,
        },
        {
            "event_id": "abc-future",
            "event_type": "earnings",
            "tickers": ["ABC"],
            "sectors": [],
            "availability_status": "available",
            "published_at_utc": "2026-01-10T16:00:00Z",
            "first_seen_at_utc": "2026-01-10T16:01:00Z",
            "direction_score": -1,
            "impact_score": 1,
        },
    ]
    archive, _ = merge_event_archive([], raw_events)
    archive_path = tmp_path / "archive.json"
    universe_path = tmp_path / "universe.csv"
    decisions_path = tmp_path / "decisions.csv"
    weights_path = tmp_path / "weights.json"
    archive_path.write_text(json.dumps(archive), encoding="utf-8")
    pd.DataFrame([{"ticker": "ABC", "sector": "tech"}, {"ticker": "XYZ", "sector": "health"}]).to_csv(universe_path, index=False)
    pd.DataFrame([{"decision_at": decision}]).to_csv(decisions_path, index=False)
    weights_path.write_text(json.dumps({"earnings": 1}), encoding="utf-8")

    panel, report = build_panel(
        str(archive_path), str(universe_path), str(decisions_path), str(weights_path)
    )

    abc = panel.loc[panel["ticker"] == "ABC"].iloc[0]
    xyz = panel.loc[panel["ticker"] == "XYZ"].iloc[0]
    assert abc["event_score"] == 1.0
    assert abc["event_score_family__earnings"] == 1.0
    assert abc["event_coverage_family__earnings"] == "available"
    assert abc["coverage_status"] == "available"
    assert pd.isna(xyz["event_score"])
    assert pd.isna(xyz["event_score_family__earnings"])
    assert xyz["event_coverage_family__earnings"] == "missing"
    assert xyz["coverage_status"] == "missing"
    assert report["archive_input_versions"] == 2
    assert report["available_score_rows"] == 1
    assert report["family_score_columns"]["earnings"]["available_rows"] == 1
    assert report["production_signal_generated"] is False


def test_panel_rejects_unversioned_archive(tmp_path):
    archive_path = tmp_path / "archive.json"
    universe_path = tmp_path / "universe.csv"
    decisions_path = tmp_path / "decisions.csv"
    weights_path = tmp_path / "weights.json"
    archive_path.write_text("[]", encoding="utf-8")
    pd.DataFrame([{"ticker": "ABC"}]).to_csv(universe_path, index=False)
    pd.DataFrame([{"decision_at": "2026-01-10T15:00:00Z"}]).to_csv(decisions_path, index=False)
    weights_path.write_text(json.dumps({"earnings": 1}), encoding="utf-8")
    # Empty archives are valid and should yield a missing-score panel.
    panel, report = build_panel(
        str(archive_path), str(universe_path), str(decisions_path), str(weights_path)
    )
    assert panel.iloc[0]["coverage_status"] == "missing"
    assert report["available_score_rows"] == 0


def test_panel_applies_default_max_age_to_prevent_stale_feed_items_from_scoring(tmp_path):
    decision = "2026-01-10T15:00:00Z"
    old_event = {
        "event_id": "abc-old",
        "event_type": "earnings",
        "tickers": ["ABC"],
        "sectors": [],
        "market_scope": "ticker",
        "availability_status": "available",
        "published_at_utc": "2026-01-01T13:00:00Z",
        "first_seen_at_utc": "2026-01-01T13:01:00Z",
        "direction_score": 1,
        "impact_score": 1,
    }
    archive, _ = merge_event_archive([], [old_event])
    archive_path = tmp_path / "archive.json"
    universe_path = tmp_path / "universe.csv"
    decisions_path = tmp_path / "decisions.csv"
    weights_path = tmp_path / "weights.json"
    archive_path.write_text(json.dumps(archive), encoding="utf-8")
    pd.DataFrame([{"ticker": "ABC", "sector": "tech"}]).to_csv(universe_path, index=False)
    pd.DataFrame([{"decision_at": decision}]).to_csv(decisions_path, index=False)
    weights_path.write_text(json.dumps({"earnings": 1}), encoding="utf-8")

    panel, report = build_panel(
        str(archive_path), str(universe_path), str(decisions_path), str(weights_path),
        default_max_age_days=3,
    )

    assert pd.isna(panel.iloc[0]["event_score"])
    assert panel.iloc[0]["coverage_status"] == "missing"
    assert report["default_max_age_days"] == 3.0
    assert report["rejection_reason_counts"]["stale_event"] >= 1
