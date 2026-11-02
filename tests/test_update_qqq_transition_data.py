# -*- coding: utf-8 -*-
"""Mocked tests for append-only QQQ/SPY/BIL data refresh."""
from pathlib import Path

import pandas as pd
import pytest

import scripts.update_qqq_transition_data as upd


def frame(dates, values):
    return pd.DataFrame({"Date": pd.to_datetime(dates), "Open": values, "Close": values,
                         "Adj Close": values})


def test_new_date_appended_and_duplicate_run_no_duplicate(tmp_path, monkeypatch):
    monkeypatch.setattr(upd, "DIR", tmp_path)
    monkeypatch.setattr(upd, "fetch", lambda t, s: frame(["2024-01-02", "2024-01-03"], [100.0, 101.0]))
    upd.main()
    assert len(pd.read_csv(tmp_path / "QQQ.csv")) == 2
    monkeypatch.setattr(upd, "fetch", lambda t, s: frame(["2024-01-02", "2024-01-03", "2024-01-04"], [100.0, 101.0, 102.0]))
    upd.main()
    assert len(pd.read_csv(tmp_path / "QQQ.csv")) == 3
    v1 = (tmp_path / "vintages.jsonl").read_text()
    upd.main()
    assert (tmp_path / "vintages.jsonl").read_text() == v1


def test_conflicting_existing_session_preserved_and_counted(tmp_path, monkeypatch):
    monkeypatch.setattr(upd, "DIR", tmp_path)
    frame(["2024-01-02"], [100.0]).to_csv(tmp_path / "QQQ.csv", index=False)
    monkeypatch.setattr(upd, "fetch", lambda t, s: frame(["2024-01-02"], [999.0]))
    upd.main()
    assert float(pd.read_csv(tmp_path / "QQQ.csv").Open.iloc[0]) == 100.0
    manifest = upd.json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["existing_session_conflicts_preserved"] > 0


def test_partial_latest_session_does_not_claim_common_asof(tmp_path, monkeypatch):
    monkeypatch.setattr(upd, "DIR", tmp_path)
    def fetch(t, s):
        dates = ["2024-01-02", "2024-01-03"] if t == "SPY" else ["2024-01-02", "2024-01-03", "2024-01-04"]
        return frame(dates, [100.0] * len(dates))
    monkeypatch.setattr(upd, "fetch", fetch)
    upd.main()
    manifest = upd.json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["asof"] == "2024-01-03"


def test_fetch_failure_does_not_update(tmp_path, monkeypatch):
    monkeypatch.setattr(upd, "DIR", tmp_path)
    def fail(t, s):
        raise RuntimeError("download failed")
    monkeypatch.setattr(upd, "fetch", fail)
    with pytest.raises(RuntimeError):
        upd.main()
    assert not (tmp_path / "QQQ.csv").exists()
