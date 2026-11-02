# -*- coding: utf-8 -*-
import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from qqq_transition_reversal_paper import (
    FILL_CSV_FIELDS,
    PaperProtocolError,
    append_event,
    apply_paper_fill,
    entry_intents,
    evaluate_observation,
    exit_intents,
    fill_event,
    initial_portfolio_state,
    order_fill_summary,
    portfolio_nav_record,
    read_fill_csv,
    replay_paper_fills,
    session_plan,
)


def test_entry_is_next_spy_session_exit_is_five_further_sessions():
    dates = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08",
             "2026-01-09", "2026-01-12", "2026-01-13"]
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


def _fill(intent, execution_id, price, quantity, *, commission=0.35, other_fees=0.02,
          fill_time_utc="2026-01-06T14:30:00Z", reference_price=None):
    return fill_event(
        intent=intent, broker_order_id=f"order-{execution_id}", execution_id=execution_id,
        fill_time_utc=fill_time_utc, fill_price=price,
        reference_price=price if reference_price is None else reference_price, quantity=quantity,
        commission=commission, other_fees=other_fees,
    )


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
    intents = exit_intents(
        trade_id="t1", signal_id="s1", exit_session="2026-01-13",
        qqq_quantity=100, estimated_proceeds=13000,
    )
    assert [(x["symbol"], x["side"]) for x in intents] == [("QQQ", "SELL"), ("BIL", "BUY")]


def test_fill_import_rejects_live_mode_invalid_prices_and_naive_time():
    intent = entry_intents(trade_id="t1", signal_id="s1", entry_session="2026-01-06")[1]
    args = dict(
        intent=intent, broker_order_id="o1", execution_id="e1",
        fill_time_utc="2026-01-06T14:30:00Z", fill_price=100, reference_price=100,
        quantity=10, commission=0.35,
    )
    with pytest.raises(PaperProtocolError):
        fill_event(**args, account_mode="LIVE")
    with pytest.raises(PaperProtocolError):
        fill_event(**{**args, "fill_price": 0})
    with pytest.raises(PaperProtocolError):
        fill_event(**{**args, "fill_time_utc": "2026-01-06T14:30:00"})


def test_fill_import_records_normalized_execution_and_fees():
    intent = entry_intents(trade_id="t1", signal_id="s1", entry_session="2026-01-06")[1]
    fill = _fill(intent, "e1", 100.2, 10)
    assert fill["account_mode"] == "PAPER"
    assert fill["fill_notional"] == 1002.0
    assert fill["total_fees"] == pytest.approx(0.37)
    assert fill["fill_time_utc"] == "2026-01-06T14:30:00Z"
    assert fill["slippage_bps"] == pytest.approx(0)
    assert fill["slippage_cost_usd"] == pytest.approx(0)


def test_fill_slippage_is_open_referenced_and_side_aware():
    intents = entry_intents(trade_id="t1", signal_id="s1", entry_session="2026-01-06")
    buy = _fill(intents[1], "buy-slip", 100.3, 100, reference_price=100)
    sell = _fill(intents[0], "sell-slip", 99.7, 100, reference_price=100)
    assert buy["slippage_bps"] == pytest.approx(30)
    assert sell["slippage_bps"] == pytest.approx(30)
    assert buy["slippage_cost_usd"] == pytest.approx(30)
    assert sell["slippage_cost_usd"] == pytest.approx(30)


def test_initial_portfolio_is_seeded_in_bil_and_nav_equals_capital():
    state = initial_portfolio_state(initial_capital=50000, bil_mark=100)
    nav = portfolio_nav_record(
        session_date="2026-01-05", state=state, qqq_mark=500, bil_mark=100,
        source_hashes={"BIL": "seed"},
    )
    assert state["bil_units"] == 500
    assert state["cash"] == 0
    assert nav["nav"] == pytest.approx(50000)
    assert nav["return_from_initial"] == pytest.approx(0)


def test_ledger_applies_buy_sell_and_deducts_fees_exactly_once():
    state = initial_portfolio_state(initial_capital=50000, bil_mark=100)
    intents = entry_intents(trade_id="t1", signal_id="s1", entry_session="2026-01-06")
    sell_bil = _fill(intents[0], "e-bil-sell", 100, 125)
    buy_qqq = _fill(intents[1], "e-qqq-buy", 500, 24)
    state = apply_paper_fill(state, sell_bil)
    state = apply_paper_fill(state, buy_qqq)
    assert state["bil_units"] == pytest.approx(375)
    assert state["qqq_units"] == pytest.approx(24)
    assert state["cash"] == pytest.approx(499.26)
    assert state["cumulative_fees"] == pytest.approx(0.74)


def test_ledger_rejects_duplicate_execution_oversell_and_insufficient_cash():
    state = initial_portfolio_state(initial_capital=50000, bil_mark=100)
    entry = entry_intents(trade_id="t1", signal_id="s1", entry_session="2026-01-06")
    sell = _fill(entry[0], "e1", 100, 125)
    state = apply_paper_fill(state, sell)
    with pytest.raises(PaperProtocolError):
        apply_paper_fill(state, sell)
    oversized_sell_intent = exit_intents(
        trade_id="t1", signal_id="s1", exit_session="2026-01-13",
        qqq_quantity=1, estimated_proceeds=1,
    )[0]
    oversized_sell = _fill(oversized_sell_intent, "e-too-many", 500, 1)
    with pytest.raises(PaperProtocolError):
        apply_paper_fill(state, oversized_sell)
    oversized_buy = _fill(entry[1], "e-overdraft", 500, 30)
    with pytest.raises(PaperProtocolError):
        apply_paper_fill(state, oversized_buy)


def test_replay_fills_matches_incremental_ledger():
    state = initial_portfolio_state(initial_capital=50000, bil_mark=100)
    intents = entry_intents(trade_id="t1", signal_id="s1", entry_session="2026-01-06")
    fills = [_fill(intents[0], "e1", 100, 125), _fill(intents[1], "e2", 500, 24)]
    incremental = apply_paper_fill(apply_paper_fill(state, fills[0]), fills[1])
    replayed = replay_paper_fills(state, fills)
    assert replayed == incremental


def test_order_fill_summary_handles_partial_unfilled_and_cancelled_orders():
    intent = entry_intents(trade_id="t1", signal_id="s1", entry_session="2026-01-06")[1]
    partial = _fill(intent, "partial-1", 500, 3)
    partial_result = order_fill_summary(
        intent=intent, fills=[partial], requested_quantity=10, broker_status="Cancelled",
    )
    assert partial_result["status"] == "PARTIALLY_FILLED_CANCELLED"
    assert partial_result["filled_quantity"] == 3
    assert partial_result["remaining_quantity"] == 7
    assert order_fill_summary(
        intent=intent, fills=[], requested_quantity=10, broker_status="Submitted",
    )["status"] == "UNFILLED"
    assert order_fill_summary(
        intent=intent, fills=[], requested_quantity=10, broker_status="Cancelled",
    )["status"] == "CANCELLED"
    filled = _fill(intent, "full-1", 500, 10)
    assert order_fill_summary(
        intent=intent, fills=[filled], requested_quantity=10, broker_status="Filled",
    )["status"] == "FILLED"


def test_order_fill_summary_rejects_overfill_and_inconsistent_filled_status():
    intent = entry_intents(trade_id="t1", signal_id="s1", entry_session="2026-01-06")[1]
    fill = _fill(intent, "overfill", 500, 11)
    with pytest.raises(PaperProtocolError):
        order_fill_summary(
            intent=intent, fills=[fill], requested_quantity=10, broker_status="Filled",
        )
    with pytest.raises(PaperProtocolError):
        order_fill_summary(
            intent=intent, fills=[_fill(intent, "short-fill", 500, 3)],
            requested_quantity=10, broker_status="Filled",
        )


def test_normalized_fill_csv_import_requires_paper_and_known_intent(tmp_path):
    intent = entry_intents(trade_id="t1", signal_id="s1", entry_session="2026-01-06")[1]
    path = tmp_path / "paper_fills.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FILL_CSV_FIELDS)
        writer.writeheader()
        writer.writerow({
            "intent_id": intent["event_id"], "account_mode": "PAPER",
            "broker_order_id": "o1", "execution_id": "e1",
            "fill_time_utc": "2026-01-06T14:30:00Z", "fill_price": "500",
            "reference_price": "499.9", "quantity": "2", "commission": "0.35", "other_fees": "0.02",
        })
    fills = read_fill_csv(path, {intent["event_id"]: intent})
    assert len(fills) == 1
    assert fills[0]["fill_notional"] == 1000
    path.write_text(path.read_text().replace(",PAPER,", ",LIVE,"))
    with pytest.raises(PaperProtocolError):
        read_fill_csv(path, {intent["event_id"]: intent})


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


def test_synthetic_full_round_trip_reconciles_four_legs_and_five_session_hold():
    sessions = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08",
                "2026-01-09", "2026-01-12", "2026-01-13"]
    plan = session_plan(sessions, sessions[0])
    observation = _obs()
    assert observation["signal"] is True
    state = initial_portfolio_state(initial_capital=50000, bil_mark=100)
    initial_nav = portfolio_nav_record(
        session_date=sessions[0], state=state, qqq_mark=500, bil_mark=100,
        source_hashes={"BIL": "synthetic-bil", "QQQ": "synthetic-qqq"},
    )
    assert initial_nav["nav"] == pytest.approx(50000)

    entry = entry_intents(
        trade_id="synthetic-trade", signal_id=observation["event_id"],
        entry_session=plan["entry_session"],
    )
    entry_fills = [
        _fill(entry[0], "sim-bil-sell", 100, 125),
        _fill(entry[1], "sim-qqq-buy", 500, 24),
    ]
    state = replay_paper_fills(state, entry_fills)
    assert state["bil_units"] == pytest.approx(375)
    assert state["qqq_units"] == pytest.approx(24)

    # Five subsequent SPY sessions elapse from the entry session to the exit session.
    qqq_during_hold = state["qqq_units"]
    for date in sessions[2:6]:
        daily = portfolio_nav_record(
            session_date=date, state=state, qqq_mark=505, bil_mark=100.4,
            source_hashes={"BIL": "synthetic-bil", "QQQ": "synthetic-qqq"},
        )
        assert daily["nav"] > 0
        assert state["qqq_units"] == qqq_during_hold == 24

    exit_orders = exit_intents(
        trade_id="synthetic-trade", signal_id=observation["event_id"],
        exit_session=plan["exit_session"], qqq_quantity=24, estimated_proceeds=12738.89,
    )
    exit_fills = [
        _fill(exit_orders[0], "sim-qqq-sell", 510, 24,
              fill_time_utc="2026-01-13T14:30:00Z"),
        _fill(exit_orders[1], "sim-bil-buy", 100.5, 122,
              fill_time_utc="2026-01-13T14:30:01Z"),
    ]
    state = replay_paper_fills(state, exit_fills)
    assert state["qqq_units"] == pytest.approx(0)
    assert state["bil_units"] == pytest.approx(497)
    assert state["cash"] == pytest.approx(477.52)
    assert state["cumulative_fees"] == pytest.approx(1.48)
    assert state["cumulative_slippage_usd"] == pytest.approx(0)

    final_nav = portfolio_nav_record(
        session_date=plan["exit_session"], state=state, qqq_mark=510, bil_mark=100.6,
        source_hashes={"BIL": "synthetic-bil", "QQQ": "synthetic-qqq"},
    )
    assert final_nav["nav"] == pytest.approx(50475.72)
    assert final_nav["execution_count"] == 4
    assert final_nav["return_from_initial"] == pytest.approx(0.0095144)



def _write_fill_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FILL_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def test_event_log_seed_intents_csv_import_and_nav_replay(tmp_path):
    from qqq_transition_reversal_paper import (
        append_order_intents,
        create_nav_from_event_log,
        import_fill_csv_to_event_log,
        load_event_log,
        seed_event_log,
    )

    event_log = tmp_path / "paper_events.jsonl"
    seed = seed_event_log(
        event_log, session_date="2026-01-05", initial_capital=50000, bil_mark=100,
    )
    assert seed["initial_bil_units"] == pytest.approx(500)
    entry = entry_intents(trade_id="cli-trade", signal_id="signal-1", entry_session="2026-01-06")
    append_order_intents(event_log, entry)
    fills_csv = tmp_path / "entry_fills.csv"
    _write_fill_csv(fills_csv, [
        {
            "intent_id": entry[0]["event_id"], "account_mode": "PAPER",
            "broker_order_id": "entry-bil", "execution_id": "entry-bil-exec",
            "fill_time_utc": "2026-01-06T14:30:00Z", "fill_price": "100",
            "reference_price": "100", "quantity": "125", "commission": "0.35",
            "other_fees": "0.02",
        },
        {
            "intent_id": entry[1]["event_id"], "account_mode": "PAPER",
            "broker_order_id": "entry-qqq", "execution_id": "entry-qqq-exec",
            "fill_time_utc": "2026-01-06T14:30:01Z", "fill_price": "500",
            "reference_price": "500", "quantity": "24", "commission": "0.35",
            "other_fees": "0.02",
        },
    ])
    imported = import_fill_csv_to_event_log(event_log, fills_csv)
    assert imported["imported_executions"] == 2
    assert imported["bil_units"] == pytest.approx(375)
    assert imported["qqq_units"] == pytest.approx(24)
    assert imported["cash"] == pytest.approx(499.26)

    nav = create_nav_from_event_log(
        event_log, session_date="2026-01-06", qqq_mark=500, bil_mark=100,
        source_hashes={"QQQ": "qqq-sha", "BIL": "bil-sha"},
    )
    assert nav["nav"] == pytest.approx(499.26 + 24 * 500 + 375 * 100)
    events = load_event_log(event_log)
    from qqq_transition_reversal_paper import replay_event_log
    assert replay_event_log(events)["execution_ids"] == ["entry-bil-exec", "entry-qqq-exec"]


def test_import_fill_csv_is_atomic_when_one_fill_overdraws(tmp_path):
    from qqq_transition_reversal_paper import (
        append_order_intents,
        import_fill_csv_to_event_log,
        load_event_log,
        seed_event_log,
    )

    event_log = tmp_path / "paper_events.jsonl"
    seed_event_log(event_log, session_date="2026-01-05", bil_mark=100)
    entry = entry_intents(trade_id="atomic-trade", signal_id="signal-2", entry_session="2026-01-06")
    append_order_intents(event_log, entry)
    fills_csv = tmp_path / "bad_fills.csv"
    _write_fill_csv(fills_csv, [
        {
            "intent_id": entry[0]["event_id"], "account_mode": "PAPER",
            "broker_order_id": "sell-bil", "execution_id": "valid-sell",
            "fill_time_utc": "2026-01-06T14:30:00Z", "fill_price": "100",
            "reference_price": "100", "quantity": "125", "commission": "0.35",
            "other_fees": "0.02",
        },
        {
            "intent_id": entry[1]["event_id"], "account_mode": "PAPER",
            "broker_order_id": "buy-qqq", "execution_id": "too-large-buy",
            "fill_time_utc": "2026-01-06T14:30:01Z", "fill_price": "500",
            "reference_price": "500", "quantity": "40", "commission": "0.35",
            "other_fees": "0.02",
        },
    ])
    before = event_log.read_text()
    with pytest.raises(PaperProtocolError, match="insufficient virtual cash"):
        import_fill_csv_to_event_log(event_log, fills_csv)
    assert event_log.read_text() == before
    assert all(event["event_type"] != "PAPER_FILL" for event in load_event_log(event_log))


def test_event_log_refuses_second_seed_or_corrupt_duplicate_ids(tmp_path):
    from qqq_transition_reversal_paper import (
        load_event_log,
        seed_event_log,
    )

    event_log = tmp_path / "paper_events.jsonl"
    seed_event_log(event_log, session_date="2026-01-05", bil_mark=100)
    with pytest.raises(PaperProtocolError, match="non-empty"):
        seed_event_log(event_log, session_date="2026-01-06", bil_mark=100)
    event_log.write_text(
        '{"event_id":"same","event_type":"A"}\n'
        '{"event_id":"same","event_type":"B"}\n'
    )
    with pytest.raises(PaperProtocolError, match="duplicate event_id"):
        load_event_log(event_log)



def test_persisting_order_intents_requires_a_seeded_paper_account(tmp_path):
    from qqq_transition_reversal_paper import append_order_intents

    intents = entry_intents(trade_id="no-seed", signal_id="s1", entry_session="2026-01-06")
    with pytest.raises(PaperProtocolError, match="exactly one PAPER_ACCOUNT_SEED"):
        append_order_intents(tmp_path / "empty.jsonl", intents)



def test_local_cli_can_seed_and_report_virtual_account(tmp_path):
    import subprocess

    script = Path(__file__).resolve().parents[1] / "scripts" / "qqq_transition_reversal_paper_reconcile.py"
    event_log = tmp_path / "cli_events.jsonl"
    seeded = subprocess.run(
        [
            sys.executable, str(script), "seed", str(event_log),
            "--date", "2026-01-05", "--bil-mark", "100",
        ],
        check=False, capture_output=True, text=True,
    )
    assert seeded.returncode == 0, seeded.stderr
    seed_result = json.loads(seeded.stdout)
    assert seed_result["event_type"] == "PAPER_ACCOUNT_SEED"

    status = subprocess.run(
        [sys.executable, str(script), "status", str(event_log)],
        check=False, capture_output=True, text=True,
    )
    assert status.returncode == 0, status.stderr
    report = json.loads(status.stdout)
    assert report["account_mode"] == "PAPER"
    assert report["initial_capital"] == pytest.approx(50000)
    assert report["bil_units"] == pytest.approx(500)
    assert report["execution_count"] == 0
