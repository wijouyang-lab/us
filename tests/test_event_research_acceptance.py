# -*- coding: utf-8 -*-
"""Tests for the unified acceptance entrypoint."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import event_research_acceptance as mod  # noqa: E402


def make_args(tmp_path, panel_last="2026-10-27", updater_status="ok", failed=0):
    panel = tmp_path / "panel.csv"
    pd.DataFrame([
        {"Date": "2026-10-26", "Ticker": "AAA", "Open": 1, "High": 2, "Low": 1, "Close": 1.5, "Volume": 10},
        {"Date": panel_last, "Ticker": "AAA", "Open": 1, "High": 2, "Low": 1, "Close": 1.5, "Volume": 10},
    ]).to_csv(panel, index=False)
    spy = tmp_path / "spy.csv"
    pd.DataFrame([
        {"Date": "2026-10-26", "Ticker": "SPY", "Open": 1, "High": 2, "Low": 1, "Close": 1.5,
         "Adj_Close": 1.5, "Volume": 10},
        {"Date": panel_last, "Ticker": "SPY", "Open": 1, "High": 2, "Low": 1, "Close": 1.6,
         "Adj_Close": 1.6, "Volume": 10},
    ]).to_csv(spy, index=False)
    events = tmp_path / "events.json"
    events.write_text("[]", encoding="utf-8")
    updater = tmp_path / "updater.json"
    updater.write_text(json.dumps({"download_status": updater_status, "failed_tickers": failed}), encoding="utf-8")
    spy_meta = tmp_path / "spy_meta.json"
    spy_meta.write_text(json.dumps({"adjusted_close_available": True}), encoding="utf-8")
    return SimpleNamespace(events=str(events), price_panel=str(panel), spy_file=str(spy),
                           spy_metadata=str(spy_meta), updater_metadata=str(updater),
                           archive_store=str(tmp_path / "archive"), as_of="2026-10-28T00:00:00Z",
                           required_date="2026-10-28", output=str(tmp_path / "out.json"))


def test_stale_close_is_pending_not_pass(tmp_path):
    args = make_args(tmp_path)
    fake = {"ready": 0, "pending": 0, "excluded": 0, "lookahead_flags": 0}
    with patch.object(mod, "readiness", return_value=fake), patch.object(
            mod, "rebuild", return_value={"runs": 1, "reproducible": True}):
        result = mod.run(args)
    assert result["exit_status"] == "pending"
    assert result["exit_code"] == 2


def test_failed_tickers_fail_closed(tmp_path):
    args = make_args(tmp_path, failed=2)
    fake = {"ready": 0, "pending": 0, "excluded": 0, "lookahead_flags": 0}
    with patch.object(mod, "readiness", return_value=fake), patch.object(
            mod, "rebuild", return_value={"runs": 1, "reproducible": True}):
        result = mod.run(args)
    assert result["exit_status"] == "fail"


def test_missing_input_raises(tmp_path):
    args = make_args(tmp_path)
    Path(args.events).unlink()
    with pytest.raises(ValueError, match="missing input"):
        mod.run(args)
