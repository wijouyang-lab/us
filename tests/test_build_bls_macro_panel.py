import pandas as pd
import pytest

from tools.research.build_bls_macro_panel import build_bls_macro_panel


def snapshot(retrieved_at, cpi, period="2026-M09"):
    return {
        "metadata": {
            "source": "us_bureau_of_labor_statistics_public_api",
            "retrieved_at_utc": retrieved_at,
            "source_payload_sha256": "hash-" + retrieved_at,
        },
        "series": [
            {
                "series_id": "CUSR0000SA0",
                "value_available": cpi is not None,
                "latest_observation": {"observation_period": period, "value": cpi} if cpi is not None else None,
            },
            {
                "series_id": "LNS14000000",
                "value_available": True,
                "latest_observation": {"observation_period": period, "value": 4.2},
            },
        ],
    }


def test_bls_panel_only_uses_snapshots_available_by_decision_time():
    decisions = pd.DataFrame({"decision_at": [
        "2026-10-23T16:00:00Z",
        "2026-10-23T18:00:00Z",
        "2026-10-24T18:00:00Z",
    ]})
    snapshots = [
        snapshot("2026-10-23T17:00:00Z", 336.2),
        snapshot("2026-10-24T17:00:00Z", 337.1, "2026-M10"),
    ]
    panel, report = build_bls_macro_panel(decisions, snapshots)
    assert pd.isna(panel.loc[0, "bls_cpi_all_items_sa"])
    assert panel.loc[0, "bls_snapshot_available"] == False
    assert panel.loc[1, "bls_cpi_all_items_sa"] == 336.2
    assert panel.loc[1, "bls_cpi_all_items_sa_observation_period"] == "2026-M09"
    assert panel.loc[2, "bls_cpi_all_items_sa"] == 337.1
    assert panel.loc[2, "bls_cpi_all_items_sa_observation_period"] == "2026-M10"
    assert report["future_snapshots_used"] is False
    assert report["historical_vintages_reconstructed"] is False
    assert report["rows_with_snapshot_available"] == 2


def test_bls_panel_preserves_missing_series_and_rejects_duplicate_snapshot_times():
    decisions = pd.DataFrame({"decision_at": ["2026-10-24T18:00:00Z"]})
    panel, _ = build_bls_macro_panel(decisions, [snapshot("2026-10-24T17:00:00Z", None)])
    assert pd.isna(panel.loc[0, "bls_cpi_all_items_sa"])
    assert panel.loc[0, "bls_cpi_all_items_sa_available"] == False
    with pytest.raises(ValueError, match="duplicate BLS snapshot retrieval timestamp"):
        build_bls_macro_panel(decisions, [
            snapshot("2026-10-24T17:00:00Z", 1.0),
            snapshot("2026-10-24T17:00:00Z", 2.0),
        ])


def test_bls_panel_rejects_invalid_decision_timestamp_and_wrong_source():
    with pytest.raises(ValueError, match="timezone-aware"):
        build_bls_macro_panel(pd.DataFrame({"decision_at": ["2026-10-24T18:00:00"]}), [])
    bad = snapshot("2026-10-24T17:00:00Z", 1.0)
    bad["metadata"]["source"] = "other"
    with pytest.raises(ValueError, match="source must be"):
        build_bls_macro_panel(pd.DataFrame({"decision_at": ["2026-10-24T18:00:00Z"]}), [bad])
