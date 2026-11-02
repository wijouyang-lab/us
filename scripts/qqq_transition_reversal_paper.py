#!/usr/bin/env python3
"""Broker-disconnected accounting and event primitives for QQQ reversal paper observation.

This module records observations, order intents, manually imported PAPER fills, and
virtual portfolio marks. It has no IBKR connection and cannot transmit or cancel orders.
"""
from __future__ import annotations

import csv
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
FILL_CSV_FIELDS = (
    "intent_id", "account_mode", "broker_order_id", "execution_id",
    "fill_time_utc", "fill_price", "reference_price", "quantity", "commission", "other_fees",
)


class PaperProtocolError(ValueError):
    """Raised when an observation or paper event violates the frozen protocol."""


def _number(value: float, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PaperProtocolError(f"{field} must be numeric") from exc
    if not math.isfinite(number):
        raise PaperProtocolError(f"{field} must be finite")
    return number


def _positive(value: float, field: str) -> float:
    number = _number(value, field)
    if number <= 0:
        raise PaperProtocolError(f"{field} must be finite and positive")
    return number


def _non_negative(value: float, field: str) -> float:
    number = _number(value, field)
    if number < 0:
        raise PaperProtocolError(f"{field} must be finite and non-negative")
    return number


def _iso_date(value: str, field: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError) as exc:
        raise PaperProtocolError(f"{field} must be YYYY-MM-DD") from exc
    if parsed.strftime("%Y-%m-%d") != value:
        raise PaperProtocolError(f"{field} must be canonical YYYY-MM-DD")
    return value


def _utc_timestamp(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PaperProtocolError("fill_time_utc is required")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise PaperProtocolError("fill_time_utc must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PaperProtocolError("fill_time_utc must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def session_plan(spy_sessions: Iterable[str], signal_date: str) -> dict:
    """Entry is next SPY session; exit is Open five further SPY sessions after entry."""
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
            try:
                ret_value = _number(qqq_ret5, "qqq_ret5")
                threshold_value = _number(threshold_5pct, "threshold_5pct")
            except PaperProtocolError:
                valid = False
                ret_value = None
                threshold_value = None
    signal_event = bool(
        valid and spy_regime == "TRANSITION" and ret_value <= threshold_value
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


def fill_event(
    *,
    intent: dict,
    broker_order_id: str,
    execution_id: str,
    fill_time_utc: str,
    fill_price: float,
    reference_price: float,
    quantity: float,
    commission: float,
    other_fees: float = 0.0,
    account_mode: str = "PAPER",
) -> dict:
    """Validate and normalize one imported Paper-account execution."""
    if account_mode != "PAPER" or intent.get("account_mode") != "PAPER":
        raise PaperProtocolError("LIVE account mode is forbidden")
    if intent.get("event_type") != "ORDER_INTENT":
        raise PaperProtocolError("fill must reference an ORDER_INTENT")
    if intent.get("symbol") not in {"QQQ", "BIL"} or intent.get("side") not in {"BUY", "SELL"}:
        raise PaperProtocolError("unsupported intent symbol or side")
    price = _positive(fill_price, "fill_price")
    reference = _positive(reference_price, "reference_price")
    qty = _positive(quantity, "quantity")
    fee = _non_negative(commission, "commission")
    other = _non_negative(other_fees, "other_fees")
    if not isinstance(broker_order_id, str) or not broker_order_id.strip():
        raise PaperProtocolError("broker_order_id is required")
    if not isinstance(execution_id, str) or not execution_id.strip():
        raise PaperProtocolError("execution_id is required")
    fill_time = _utc_timestamp(fill_time_utc)
    notional = price * qty
    slippage_per_unit = price - reference if intent["side"] == "BUY" else reference - price
    slippage_bps = slippage_per_unit / reference * 10_000.0
    slippage_cost = slippage_per_unit * qty
    return {
        "event_type": "PAPER_FILL",
        "event_id": hashlib.sha256(f"{execution_id}|{intent['event_id']}".encode()).hexdigest(),
        "intent_id": intent["event_id"],
        "trade_id": intent["trade_id"],
        "signal_id": intent["signal_id"],
        "symbol": intent["symbol"],
        "side": intent["side"],
        "account_mode": "PAPER",
        "currency": "USD",
        "broker_order_id": broker_order_id.strip(),
        "broker_execution_id": execution_id.strip(),
        "fill_time_utc": fill_time,
        "fill_price": price,
        "reference_price": reference,
        "slippage_bps": slippage_bps,
        "slippage_cost_usd": slippage_cost,
        "quantity": qty,
        "fill_notional": notional,
        "commission": fee,
        "other_fees": other,
        "total_fees": fee + other,
    }


def initial_portfolio_state(
    *, initial_capital: float = INITIAL_CAPITAL, bil_mark: float,
) -> dict:
    """Seed the virtual account in BIL so idle capital earns the chosen cash proxy."""
    capital = _positive(initial_capital, "initial_capital")
    mark = _positive(bil_mark, "bil_mark")
    return {
        "account_mode": "PAPER",
        "initial_capital": capital,
        "cash": 0.0,
        "qqq_units": 0.0,
        "bil_units": capital / mark,
        "cumulative_fees": 0.0,
        "cumulative_slippage_usd": 0.0,
        "execution_ids": [],
    }


def apply_paper_fill(state: dict, fill: dict) -> dict:
    """Apply one execution once; debit/credit cash and units and charge fees exactly once."""
    if state.get("account_mode") != "PAPER" or fill.get("account_mode") != "PAPER":
        raise PaperProtocolError("only PAPER fills can be applied")
    if fill.get("event_type") != "PAPER_FILL":
        raise PaperProtocolError("only PAPER_FILL events can change the ledger")
    execution_id = fill.get("broker_execution_id")
    if not execution_id:
        raise PaperProtocolError("broker_execution_id is required")
    seen = list(state.get("execution_ids", []))
    if execution_id in seen:
        raise PaperProtocolError(f"duplicate broker execution: {execution_id}")
    symbol = fill.get("symbol")
    side = fill.get("side")
    if symbol not in {"QQQ", "BIL"} or side not in {"BUY", "SELL"}:
        raise PaperProtocolError("unsupported fill symbol or side")
    price = _positive(fill.get("fill_price"), "fill_price")
    reference = _positive(fill.get("reference_price"), "reference_price")
    quantity = _positive(fill.get("quantity"), "quantity")
    notional = price * quantity
    slippage_per_unit = price - reference if side == "BUY" else reference - price
    expected_slippage_bps = slippage_per_unit / reference * 10_000.0
    expected_slippage_cost = slippage_per_unit * quantity
    reported_slippage_bps = _number(fill.get("slippage_bps"), "slippage_bps")
    reported_slippage_cost = _number(fill.get("slippage_cost_usd"), "slippage_cost_usd")
    if not math.isclose(expected_slippage_bps, reported_slippage_bps, rel_tol=1e-10, abs_tol=1e-7):
        raise PaperProtocolError("slippage_bps does not match fill/reference prices")
    if not math.isclose(expected_slippage_cost, reported_slippage_cost, rel_tol=1e-10, abs_tol=1e-7):
        raise PaperProtocolError("slippage_cost_usd does not match fill/reference prices")
    reported_notional = _positive(fill.get("fill_notional"), "fill_notional")
    if not math.isclose(notional, reported_notional, rel_tol=1e-10, abs_tol=1e-7):
        raise PaperProtocolError("fill_notional does not equal fill_price * quantity")
    commission = _non_negative(fill.get("commission"), "commission")
    other_fees = _non_negative(fill.get("other_fees"), "other_fees")
    fees = commission + other_fees
    reported_fees = _non_negative(fill.get("total_fees"), "total_fees")
    if not math.isclose(fees, reported_fees, rel_tol=1e-10, abs_tol=1e-7):
        raise PaperProtocolError("total_fees does not equal commission + other_fees")

    cash = _non_negative(state.get("cash"), "cash")
    qqq_units = _non_negative(state.get("qqq_units"), "qqq_units")
    bil_units = _non_negative(state.get("bil_units"), "bil_units")
    if side == "BUY":
        required_cash = notional + fees
        if required_cash > cash + 1e-7:
            raise PaperProtocolError(
                f"insufficient virtual cash for {symbol} buy: need {required_cash:.8f}, have {cash:.8f}"
            )
        cash -= required_cash
        if symbol == "QQQ":
            qqq_units += quantity
        else:
            bil_units += quantity
    else:
        available = qqq_units if symbol == "QQQ" else bil_units
        if quantity > available + 1e-8:
            raise PaperProtocolError(
                f"cannot sell {quantity:.8f} {symbol}; only {available:.8f} available"
            )
        proceeds = notional - fees
        if proceeds < -1e-7:
            raise PaperProtocolError("fees exceed sell proceeds")
        cash += max(0.0, proceeds)
        if symbol == "QQQ":
            qqq_units = max(0.0, qqq_units - quantity)
        else:
            bil_units = max(0.0, bil_units - quantity)

    updated = dict(state)
    updated.update({
        "cash": max(0.0, cash),
        "qqq_units": qqq_units,
        "bil_units": bil_units,
        "cumulative_fees": _non_negative(state.get("cumulative_fees", 0.0), "cumulative_fees") + fees,
        "cumulative_slippage_usd": _number(state.get("cumulative_slippage_usd", 0.0), "cumulative_slippage_usd") + expected_slippage_cost,
        "execution_ids": seen + [execution_id],
    })
    return updated


def replay_paper_fills(initial_state: dict, fills: Iterable[dict]) -> dict:
    """Rebuild a virtual portfolio deterministically from its seed state and fills."""
    state = dict(initial_state)
    state["execution_ids"] = list(initial_state.get("execution_ids", []))
    for fill in fills:
        state = apply_paper_fill(state, fill)
    return state


def order_fill_summary(
    *, intent: dict, fills: Iterable[dict], requested_quantity: float, broker_status: str,
) -> dict:
    """Summarize partial/unfilled/cancelled executions without inventing a fill."""
    requested = _positive(requested_quantity, "requested_quantity")
    matching = list(fills)
    total_quantity = 0.0
    total_notional = 0.0
    total_fees = 0.0
    execution_ids: set[str] = set()
    for fill in matching:
        if fill.get("intent_id") != intent.get("event_id"):
            raise PaperProtocolError("fill does not belong to the supplied intent")
        execution_id = fill.get("broker_execution_id")
        if not execution_id or execution_id in execution_ids:
            raise PaperProtocolError("missing or duplicate execution ID in order summary")
        execution_ids.add(execution_id)
        total_quantity += _positive(fill.get("quantity"), "quantity")
        total_notional += _positive(fill.get("fill_notional"), "fill_notional")
        total_fees += _non_negative(fill.get("total_fees"), "total_fees")
    if total_quantity > requested + 1e-8:
        raise PaperProtocolError("filled quantity exceeds requested quantity")
    remaining = max(0.0, requested - total_quantity)
    status = str(broker_status).strip().lower()
    if status == "filled":
        if not math.isclose(total_quantity, requested, rel_tol=1e-8, abs_tol=1e-8):
            raise PaperProtocolError("broker says Filled but imported execution quantity is incomplete")
        normalized = "FILLED"
    elif status in {"cancelled", "canceled"}:
        normalized = "PARTIALLY_FILLED_CANCELLED" if total_quantity > 0 else "CANCELLED"
    elif status in {"submitted", "presubmitted", "apipending", "pendingsubmit", "pendingcancel"}:
        normalized = "PARTIALLY_FILLED" if total_quantity > 0 else "UNFILLED"
    elif status == "inactive":
        normalized = "PARTIALLY_FILLED_INACTIVE" if total_quantity > 0 else "INACTIVE"
    else:
        raise PaperProtocolError(f"unsupported broker status: {broker_status}")
    return {
        "event_type": "ORDER_RECONCILIATION",
        "intent_id": intent["event_id"],
        "broker_status": broker_status,
        "status": normalized,
        "requested_quantity": requested,
        "filled_quantity": total_quantity,
        "remaining_quantity": remaining,
        "fill_notional": total_notional,
        "total_fees": total_fees,
        "execution_count": len(execution_ids),
    }


def read_fill_csv(path: Path, intents_by_id: dict[str, dict]) -> list[dict]:
    """Read a normalized, account-ID-free execution CSV exported from a PAPER workflow."""
    path = Path(path)
    if not path.exists():
        raise PaperProtocolError(f"fill CSV does not exist: {path}")
    fills = []
    seen_execution_ids: set[str] = set()
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or not set(FILL_CSV_FIELDS).issubset(reader.fieldnames):
                raise PaperProtocolError("fill CSV must contain: " + ", ".join(FILL_CSV_FIELDS))
            for row_number, row in enumerate(reader, start=2):
                if not any((value or "").strip() for value in row.values()):
                    continue
                intent_id = (row.get("intent_id") or "").strip()
                intent = intents_by_id.get(intent_id)
                if intent is None:
                    raise PaperProtocolError(f"row {row_number}: unknown intent_id")
                execution_id = (row.get("execution_id") or "").strip()
                if not execution_id or execution_id in seen_execution_ids:
                    raise PaperProtocolError(f"row {row_number}: missing or duplicate execution_id")
                seen_execution_ids.add(execution_id)
                try:
                    fill = fill_event(
                        intent=intent,
                        broker_order_id=(row.get("broker_order_id") or "").strip(),
                        execution_id=execution_id,
                        fill_time_utc=(row.get("fill_time_utc") or "").strip(),
                        fill_price=float(row["fill_price"]),
                        reference_price=float(row["reference_price"]),
                        quantity=float(row["quantity"]),
                        commission=float(row["commission"]),
                        other_fees=float(row["other_fees"]),
                        account_mode=(row.get("account_mode") or "").strip(),
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    if isinstance(exc, PaperProtocolError):
                        raise
                    raise PaperProtocolError(f"row {row_number}: invalid numeric field") from exc
                fills.append(fill)
    except UnicodeDecodeError as exc:
        raise PaperProtocolError("fill CSV must be UTF-8 encoded") from exc
    return fills


def nav_record(
    *,
    session_date: str,
    cash: float,
    qqq_units: float,
    bil_units: float,
    qqq_mark: float,
    bil_mark: float,
    cumulative_fees: float,
    source_hashes: dict[str, str],
    cumulative_slippage_usd: float = 0.0,
) -> dict:
    """Create one mark-to-market record; fees already reduce cash and are not deducted again."""
    session_date = _iso_date(session_date, "session_date")
    cash = _non_negative(cash, "cash")
    qqq_units = _non_negative(qqq_units, "qqq_units")
    bil_units = _non_negative(bil_units, "bil_units")
    cumulative_fees = _non_negative(cumulative_fees, "cumulative_fees")
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
        "cumulative_slippage_usd": _number(cumulative_slippage_usd, "cumulative_slippage_usd"),
        "nav": nav,
        "source_hashes": dict(sorted(source_hashes.items())),
    }


def portfolio_nav_record(
    *, session_date: str, state: dict, qqq_mark: float, bil_mark: float,
    source_hashes: dict[str, str],
) -> dict:
    """Create NAV directly from the reconciled cash/share ledger."""
    if state.get("account_mode") != "PAPER":
        raise PaperProtocolError("only PAPER ledger state can be marked")
    record = nav_record(
        session_date=session_date,
        cash=state["cash"],
        qqq_units=state["qqq_units"],
        bil_units=state["bil_units"],
        qqq_mark=qqq_mark,
        bil_mark=bil_mark,
        cumulative_fees=state["cumulative_fees"],
        source_hashes=source_hashes,
        cumulative_slippage_usd=state.get("cumulative_slippage_usd", 0.0),
    )
    record["initial_capital"] = _positive(state["initial_capital"], "initial_capital")
    record["return_from_initial"] = record["nav"] / record["initial_capital"] - 1.0
    record["execution_count"] = len(state.get("execution_ids", []))
    return record


def append_event(path: Path, event: dict) -> None:
    """Append one JSONL event. Duplicate IDs/corrupt existing logs fail closed."""
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



def load_event_log(path: Path) -> list[dict]:
    """Load and validate an append-only JSONL event log."""
    path = Path(path)
    if not path.exists():
        return []
    events: list[dict] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise PaperProtocolError(
                    f"event log is corrupt at line {line_number}; refusing to continue"
                ) from exc
            if not isinstance(event, dict) or not event.get("event_id"):
                raise PaperProtocolError(f"event log line {line_number} lacks an event_id")
            event_id = event["event_id"]
            if event_id in seen:
                raise PaperProtocolError(f"duplicate event_id in log: {event_id}")
            seen.add(event_id)
            events.append(event)
    return events


def account_seed_event(
    *, session_date: str, initial_capital: float = INITIAL_CAPITAL, bil_mark: float,
) -> dict:
    """Create a deterministic opening event for a virtual account initially held in BIL."""
    session_date = _iso_date(session_date, "session_date")
    capital = _positive(initial_capital, "initial_capital")
    mark = _positive(bil_mark, "bil_mark")
    event_id = hashlib.sha256(
        f"paper-seed|{session_date}|{capital:.8f}|{mark:.8f}".encode()
    ).hexdigest()
    return {
        "event_type": "PAPER_ACCOUNT_SEED",
        "event_id": event_id,
        "account_mode": "PAPER",
        "session_date": session_date,
        "currency": "USD",
        "initial_capital": capital,
        "initial_bil_mark": mark,
        "initial_bil_units": capital / mark,
        "qqq_units": 0.0,
        "cash": 0.0,
    }


def replay_event_log(events: Iterable[dict]) -> dict:
    """Reconstruct ledger state from one seed and all subsequent PAPER_FILL events."""
    rows = list(events)
    seeds = [i for i, event in enumerate(rows) if event.get("event_type") == "PAPER_ACCOUNT_SEED"]
    if len(seeds) != 1:
        raise PaperProtocolError("event log must contain exactly one PAPER_ACCOUNT_SEED")
    seed_index = seeds[0]
    seed = rows[seed_index]
    if seed_index != 0:
        raise PaperProtocolError("PAPER_ACCOUNT_SEED must be the first event in the log")
    if seed.get("account_mode") != "PAPER" or seed.get("currency") != "USD":
        raise PaperProtocolError("account seed must be PAPER USD")
    state = initial_portfolio_state(
        initial_capital=seed["initial_capital"],
        bil_mark=seed["initial_bil_mark"],
    )
    if not math.isclose(
        state["bil_units"], _positive(seed["initial_bil_units"], "initial_bil_units"),
        rel_tol=1e-10, abs_tol=1e-8,
    ):
        raise PaperProtocolError("seed BIL units do not reconcile to initial capital and mark")
    fills = []
    for event in rows[seed_index + 1:]:
        if event.get("event_type") == "PAPER_FILL":
            fills.append(event)
    return replay_paper_fills(state, fills)


def append_order_intents(path: Path, intents: Iterable[dict]) -> list[dict]:
    """Persist intents after checking their type and PAPER-only execution boundary."""
    rows = list(intents)
    for intent in rows:
        if intent.get("event_type") != "ORDER_INTENT" or intent.get("account_mode") != "PAPER":
            raise PaperProtocolError("only PAPER ORDER_INTENT events can be persisted")
    for intent in rows:
        append_event(path, intent)
    return rows


def import_fill_csv_to_event_log(path: Path, csv_path: Path) -> dict:
    """Validate the entire normalized CSV against existing intents and ledger before appending."""
    events = load_event_log(path)
    current_state = replay_event_log(events)
    intents = {
        event["event_id"]: event
        for event in events
        if event.get("event_type") == "ORDER_INTENT"
    }
    parsed = read_fill_csv(csv_path, intents)
    existing_execution_ids = {
        event.get("broker_execution_id")
        for event in events
        if event.get("event_type") == "PAPER_FILL"
    }
    existing_execution_ids.discard(None)
    for fill in parsed:
        execution_id = fill["broker_execution_id"]
        if execution_id in existing_execution_ids:
            raise PaperProtocolError(f"execution already exists in event log: {execution_id}")
        existing_execution_ids.add(execution_id)
    # Apply all candidate fills in memory first. A bad row prevents any partial append.
    trial_state = replay_paper_fills(current_state_seed(events), [
        event for event in events if event.get("event_type") == "PAPER_FILL"
    ])
    for fill in sorted(parsed, key=lambda item: item["fill_time_utc"]):
        trial_state = apply_paper_fill(trial_state, fill)
    for fill in sorted(parsed, key=lambda item: item["fill_time_utc"]):
        append_event(path, fill)
    return {
        "imported_executions": len(parsed),
        "execution_ids": [fill["broker_execution_id"] for fill in parsed],
        "cash": trial_state["cash"],
        "qqq_units": trial_state["qqq_units"],
        "bil_units": trial_state["bil_units"],
        "cumulative_fees": trial_state["cumulative_fees"],
        "cumulative_slippage_usd": trial_state.get("cumulative_slippage_usd", 0.0),
    }


def current_state_seed(events: Iterable[dict]) -> dict:
    """Return the opening state reconstructed from the unique seed event."""
    rows = list(events)
    seeds = [event for event in rows if event.get("event_type") == "PAPER_ACCOUNT_SEED"]
    if len(seeds) != 1:
        raise PaperProtocolError("event log must contain exactly one PAPER_ACCOUNT_SEED")
    seed = seeds[0]
    if rows.index(seed) != 0:
        raise PaperProtocolError("PAPER_ACCOUNT_SEED must be the first event in the log")
    return initial_portfolio_state(
        initial_capital=seed["initial_capital"],
        bil_mark=seed["initial_bil_mark"],
    )


def seed_event_log(
    path: Path, *, session_date: str, initial_capital: float = INITIAL_CAPITAL, bil_mark: float,
) -> dict:
    """Create the account seed only in an empty log; never reset an existing ledger."""
    path = Path(path)
    existing = load_event_log(path)
    if existing:
        raise PaperProtocolError("refusing to seed a non-empty event log")
    seed = account_seed_event(
        session_date=session_date, initial_capital=initial_capital, bil_mark=bil_mark,
    )
    append_event(path, seed)
    return seed


def create_nav_from_event_log(
    path: Path,
    *,
    session_date: str,
    qqq_mark: float,
    bil_mark: float,
    source_hashes: dict[str, str],
) -> dict:
    """Rebuild the current ledger and append one NAV mark for the requested session."""
    events = load_event_log(path)
    state = replay_event_log(events)
    record = portfolio_nav_record(
        session_date=session_date,
        state=state,
        qqq_mark=qqq_mark,
        bil_mark=bil_mark,
        source_hashes=source_hashes,
    )
    append_event(path, record)
    return record
