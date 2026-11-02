# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from qqq_transition_reversal_paper import (
    PaperProtocolError, append_event, entry_intents, evaluate_observation,
    exit_intents, fill_event, nav_record, session_plan,
)


def test_entry_is_next_spy_session_exit_is_five_further_sessions():
    dates = [f"2026-01-{d:02d}" for d in range(5, 20)]
    plan = session_plan(dates, dates[0])
    assert plan["entry_session"] == dates[1]
    assert plan["exit_session"] == dates[6]
    assert plan["hold_sessions_after_entry"] == 5


def test_session_plan_rejects_unsorted_duplicate_and_missing_signal_date():
    with pytest.raises(PaperProtocolError):
        session_plan(["2026-01-06", "2026-01-05"], "2026-01-05")
    with pytest.raises(PaperProtocolError):
        session_plan(["2026-01-05", "2026-01-05"], "2026-01-05")
    with pytest.raises(PaperProtocolError):
        session_plan(["2026-01-05"], "2026-01-06")


def test_session_plan_requires_full_exit_horizon():
    with pytest.raises(PaperProtocolError):
        session_plan(["2026-01-05", "2026-01-06"], "2026-01-05")


def _obs(**overrides):
    values = dict(
        session_date="2026-01-05", data_asof_date="2026-01-05",
        qqq_ret5=-0.10, threshold_5pct=-0.05, spy_regime="TRANSITION",
        data_valid=True, position_open=False, pending_entry=False,
        code_sha="abc123", input_hashes={"QQQ": "a", "SPY": "b", "BIL": "c"},
    )
    values.update(overrides)
    return evaluate_observation(**values)


def test_signal_only_after_completed_transition_session():
    obs = _obs()
    assert obs["signal"] is True
    assert obs["reason"] == "SIGNAL"


def test_invalid_or_stale_data_fails_closed():
    assert _obs(data_asof_date="2026-01-04")["signal"] is False
    assert _obs(data_valid=False)["reason"] == "INVALID_OR_STALE_DATA"
    assert _obs(qqq_ret5=float("nan"))["signal"] is False


def test_non_transition_and_no_event_do_not_signal():
    assert not _obs(spy_regime="RISK_ON")["signal"]
    assert not _obs(qqq_ret5=-0.01)["signal"]


def test_overlapping_signal_is_logged_and_suppressed():
    obs = _obs(position_open=True)
    assert obs["signal_event"] is True
    assert obs["overlap_skipped"] is True
    assert obs["signal"] is False


def test_entry_intents_are_two_paper_only_non_transmitting_legs():
    intents = entry_intents(trade_id="t1", signal_id="s1", entry_session="2026-01-06")
    assert [(x["symbol"], x["side"]) for x in intents] == [("BIL", "SELL"), ("QQQ", "BUY")]
    assert all(x["account_mode"] == "PAPER" and x["status"] == "INTENT_ONLY" for x in intents)
    assert all(x["outside_rth"] is False for x in intents)
    assert intents[0]["amount"] == 12500.0


def test_exit_intents_are_qqq_sell_and_bil_buy():
    intents = exit_intents(trade_id="t1", signal_id="s1", exit_session="2026-01-13",
                           qqq_quantity=100, estimated_proceeds=13000)
    assert [(x["symbol"], x["side"]) for x in intents] == [("QQQ", "SELL"), ("BIL", "BUY")]


def test_fill_import_rejects_live_mode_and_invalid_prices():
    intent = entry_intents(trade_id="t1", signal_id="s1", entry_session="2026-01-06")[1]
    args = dict(intent=intent, broker_order_id="o1", execution_id="e1",
                fill_time_utc="2026-01-06T14:30:00Z", fill_price=100,
                quantity=10, commission=0.35)
    with pytest.raises(PaperProtocolError):
        fill_event(**args, account_mode="LIVE")
    with pytest.raises(PaperProtocolError):
        fill_event(**{**args, "fill_price": 0})


def test_fill_import_records_actual_broker_execution_and_fees():
    intent = entry_intents(trade_id="t1", signal_id="s1", entry_session="2026-01-06")[1]
    fill = fill_event(intent=intent, broker_order_id="o1", execution_id="e1",
                      fill_time_utc="2026-01-06T14:30:00Z", fill_price=100.2,
                      quantity=10, commission=0.35, other_fees=0.02)
    assert fill["account_mode"] == "PAPER"
    assert fill["fill_notional"] == 1002.0
    assert fill["total_fees"] == pytest.approx(0.37)


def test_nav_marks_assets_and_rejects_negative_cash():
    nav = nav_record(session_date="2026-01-06", cash=100, qqq_units=10, bil_units=20,
                     qqq_mark=100, bil_mark=90, cumulative_fees=1, source_hashes={})
    assert nav["nav"] == 2900
    with pytest.raises(PaperProtocolError):
        nav_record(session_date="2026-01-06", cash=-1, qqq_units=0, bil_units=0,
                   qqq_mark=100, bil_mark=90, cumulative_fees=0, source_hashes={})


def test_append_only_log_rejects_duplicate_and_corruption(tmp_path):
    path = tmp_path / "events.jsonl"
    event = {"event_id": "one", "event_type": "TEST"}
    append_event(path, event)
    assert json.loads(path.read_text().splitlines()[0]) == event
    with pytest.raises(PaperProtocolError):
        append_event(path, event)
    path.write_text("{bad json}\n")
    with pytest.raises(PaperProtocolError):
        append_event(path, {"event_id": "two"})
