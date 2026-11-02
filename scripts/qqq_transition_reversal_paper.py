#!/usr/bin/env python3
"""Safe, broker-disconnected event primitives for QQQ reversal paper observation.

This module creates observations and order-intent records only. It cannot connect to
IBKR, submit orders, or select a live account.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

INITIAL_CAPITAL = 50_000.0
STRATEGY_WEIGHT = 0.25
STRATEGY_NOTIONAL = INITIAL_CAPITAL * STRATEGY_WEIGHT
HOLD_SESSIONS_AFTER_ENTRY = 5
PROTOCOL_VERSION = "qqq-transition-reversal-paper-v1"


class PaperProtocolError(ValueError):
    """Raised when an observation or paper event violates the frozen protocol."""


def _positive(value: float, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PaperProtocolError(f"{field} must be numeric") from exc
    if not math.isfinite(number) or number <= 0:
        raise PaperProtocolError(f"{field} must be finite and positive")
    return number


def _iso_date(value: str, field: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError) as exc:
        raise PaperProtocolError(f"{field} must be YYYY-MM-DD") from exc
    if parsed.strftime("%Y-%m-%d") != value:
        raise PaperProtocolError(f"{field} must be canonical YYYY-MM-DD")
    return value


def session_plan(spy_sessions: Iterable[str], signal_date: str) -> dict:
    """Entry is next SPY session; exit is Open five further SPY sessions later."""
    sessions = [_iso_date(x, "SPY session") for x in spy_sessions]
    if sessions != sorted(set(sessions)):
        raise PaperProtocolError("SPY sessions must be strictly increasing and unique")
    signal_date = _iso_date(signal_date, "signal_date")
    try:
        signal_idx = sessions.index(signal_date)
    except ValueError as exc:
        raise PaperProtocolError("signal_date is not on the SPY calendar") from exc
    entry_idx = signal_idx + 1
    exit_idx = entry_idx + HOLD_SESSIONS_AFTER_ENTRY
    if exit_idx >= len(sessions):
        raise PaperProtocolError("SPY calendar does not yet contain the scheduled exit")
    return {
        "signal_date": signal_date,
        "entry_session": sessions[entry_idx],
        "exit_session": sessions[exit_idx],
        "hold_sessions_after_entry": HOLD_SESSIONS_AFTER_ENTRY,
    }


def evaluate_observation(
    *,
    session_date: str,
    data_asof_date: str,
    qqq_ret5: float | None,
    threshold_5pct: float | None,
    spy_regime: str | None,
    data_valid: bool,
    position_open: bool,
    pending_entry: bool,
    code_sha: str,
    input_hashes: dict[str, str],
) -> dict:
    """Evaluate one completed-close observation; invalid/stale data fail closed."""
    session_date = _iso_date(session_date, "session_date")
    data_asof_date = _iso_date(data_asof_date, "data_asof_date")
    valid = bool(data_valid and data_asof_date == session_date)
    ret_value = None
    threshold_value = None
    if valid:
        if qqq_ret5 is None or threshold_5pct is None:
            valid = False
        else:
            ret_value = float(qqq_ret5)
            threshold_value = float(threshold_5pct)
            valid = math.isfinite(ret_value) and math.isfinite(threshold_value)
    signal_event = bool(
        valid
        and spy_regime == "TRANSITION"
        and ret_value <= threshold_value
    )
    overlap = bool(signal_event and (position_open or pending_entry))
    signal = bool(signal_event and not overlap)
    payload = {
        "protocol_version": PROTOCOL_VERSION,
        "session_date": session_date,
        "data_asof_date": data_asof_date,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "code_sha": str(code_sha),
        "input_hashes": dict(sorted(input_hashes.items())),
        "lookback": 252,
        "quantile": 0.05,
        "hold_sessions_after_entry": HOLD_SESSIONS_AFTER_ENTRY,
        "qqq_ret5": ret_value,
        "threshold_5pct": threshold_value,
        "spy_regime": spy_regime,
        "data_valid": valid,
        "signal_event": signal_event,
        "overlap_skipped": overlap,
        "signal": signal,
        "reason": (
            "INVALID_OR_STALE_DATA" if not valid else
            "OVERLAP_SKIPPED" if overlap else
            "SIGNAL" if signal else
            "NO_SIGNAL"
        ),
    }
    payload["event_id"] = hashlib.sha256(
        f"observation|{session_date}|{code_sha}|{json.dumps(input_hashes, sort_keys=True)}".encode()
    ).hexdigest()
    return payload


def entry_intents(*, trade_id: str, signal_id: str, entry_session: str) -> list[dict]:
    """Create two intents only; no order is transmitted to a broker."""
    entry_session = _iso_date(entry_session, "entry_session")
    if not trade_id or not signal_id:
        raise PaperProtocolError("trade_id and signal_id are required")
    legs = [
        ("BIL", "SELL", "BIL_TO_QQQ", STRATEGY_NOTIONAL),
        ("QQQ", "BUY", "BIL_TO_QQQ", STRATEGY_NOTIONAL),
    ]
    return [_intent(trade_id, signal_id, entry_session, *leg) for leg in legs]


def exit_intents(
    *, trade_id: str, signal_id: str, exit_session: str, qqq_quantity: float,
    estimated_proceeds: float,
) -> list[dict]:
    """Create QQQ sell and BIL buy intents after the frozen five-session hold."""
    exit_session = _iso_date(exit_session, "exit_session")
    qqq_quantity = _positive(qqq_quantity, "qqq_quantity")
    estimated_proceeds = _positive(estimated_proceeds, "estimated_proceeds")
    if not trade_id or not signal_id:
        raise PaperProtocolError("trade_id and signal_id are required")
    legs = [
        ("QQQ", "SELL", "QQQ_TO_BIL", qqq_quantity),
        ("BIL", "BUY", "QQQ_TO_BIL", estimated_proceeds),
    ]
    return [_intent(trade_id, signal_id, exit_session, *leg) for leg in legs]


def _intent(trade_id, signal_id, session, symbol, side, leg, amount):
    order_id = hashlib.sha256(
        f"{trade_id}|{session}|{symbol}|{side}|{leg}".encode()
    ).hexdigest()
    return {
        "event_type": "ORDER_INTENT",
        "event_id": order_id,
        "trade_id": trade_id,
        "signal_id": signal_id,
        "symbol": symbol,
        "side": side,
        "leg": leg,
        "planned_session": session,
        "amount": float(amount),
        "amount_type": "SHARES" if symbol == "QQQ" and side == "SELL" else "USD_NOTIONAL",
        "account_mode": "PAPER",
        "order_type": "MARKET",
        "time_in_force": "DAY",
        "outside_rth": False,
        "status": "INTENT_ONLY",
    }


def fill_event(*, intent: dict, broker_order_id: str, execution_id: str,
               fill_time_utc: str, fill_price: float, quantity: float,
               commission: float, other_fees: float = 0.0,
               account_mode: str = "PAPER") -> dict:
    """Validate and normalize a manually imported Paper-account execution."""
    if account_mode != "PAPER" or intent.get("account_mode") != "PAPER":
        raise PaperProtocolError("LIVE account mode is forbidden")
    if intent.get("event_type") != "ORDER_INTENT":
        raise PaperProtocolError("fill must reference an ORDER_INTENT")
    price = _positive(fill_price, "fill_price")
    qty = _positive(quantity, "quantity")
    fee = float(commission)
    other = float(other_fees)
    if not math.isfinite(fee) or fee < 0 or not math.isfinite(other) or other < 0:
        raise PaperProtocolError("fees must be finite and non-negative")
    if not broker_order_id or not execution_id or not fill_time_utc:
        raise PaperProtocolError("broker order, execution ID, and fill time are required")
    return {
        "event_type": "PAPER_FILL",
        "event_id": hashlib.sha256(f"{execution_id}|{intent['event_id']}".encode()).hexdigest(),
        "intent_id": intent["event_id"],
        "trade_id": intent["trade_id"],
        "signal_id": intent["signal_id"],
        "symbol": intent["symbol"],
        "side": intent["side"],
        "account_mode": "PAPER",
        "broker_order_id": str(broker_order_id),
        "broker_execution_id": str(execution_id),
        "fill_time_utc": str(fill_time_utc),
        "fill_price": price,
        "quantity": qty,
        "fill_notional": price * qty,
        "commission": fee,
        "other_fees": other,
        "total_fees": fee + other,
    }


def nav_record(*, session_date: str, cash: float, qqq_units: float,
               bil_units: float, qqq_mark: float, bil_mark: float,
               cumulative_fees: float, source_hashes: dict[str, str]) -> dict:
    """Mark-to-market NAV record; values must be reconciled to the fill ledger."""
    session_date = _iso_date(session_date, "session_date")
    values = [float(cash), float(qqq_units), float(bil_units), float(cumulative_fees)]
    if not all(math.isfinite(x) for x in values) or cash < 0 or qqq_units < 0 or bil_units < 0 or cumulative_fees < 0:
        raise PaperProtocolError("cash, units, and fees must be finite and non-negative")
    qmark = _positive(qqq_mark, "qqq_mark")
    bmark = _positive(bil_mark, "bil_mark")
    qvalue, bvalue = qqq_units * qmark, bil_units * bmark
    nav = cash + qvalue + bvalue
    return {
        "event_type": "DAILY_NAV",
        "event_id": hashlib.sha256(f"nav|{session_date}".encode()).hexdigest(),
        "date": session_date,
        "cash": cash,
        "qqq_units": qqq_units,
        "bil_units": bil_units,
        "qqq_mark": qmark,
        "bil_mark": bmark,
        "qqq_value": qvalue,
        "bil_value": bvalue,
        "cumulative_fees": cumulative_fees,
        "nav": nav,
        "source_hashes": dict(sorted(source_hashes.items())),
    }


def append_event(path: Path, event: dict) -> None:
    """Append one JSONL event. Duplicate event IDs are rejected; existing rows never mutate."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    event_id = event.get("event_id")
    if not event_id:
        raise PaperProtocolError("event_id is required")
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    existing = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise PaperProtocolError("existing event log is corrupt; refusing append") from exc
                if existing.get("event_id") == event_id:
                    raise PaperProtocolError(f"duplicate event_id: {event_id}")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
