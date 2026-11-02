#!/usr/bin/env python3
"""Command-line operator for the broker-disconnected QQQ reversal paper ledger.

This script never connects to IBKR and never submits or cancels orders.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qqq_transition_reversal_paper import (  # noqa: E402
    PaperProtocolError,
    append_order_intents,
    create_nav_from_event_log,
    entry_intents,
    exit_intents,
    import_fill_csv_to_event_log,
    import_order_status_csv_to_event_log,
    load_event_log,
    replay_event_log,
    record_manual_preflight,
    seed_event_log,
)


def _json(value: dict) -> None:
    print(json.dumps(value, sort_keys=True, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record/reconcile QQQ reversal paper events; no brokerage connection."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    seed = sub.add_parser("seed", help="create the initial virtual $50,000 BIL account")
    seed.add_argument("events", type=Path, help="append-only JSONL event log")
    seed.add_argument("--date", required=True, help="opening session YYYY-MM-DD")
    seed.add_argument("--bil-mark", required=True, type=float, help="opening BIL mark in USD")
    seed.add_argument("--initial-capital", type=float, default=50_000.0)

    entry = sub.add_parser("entry-intents", help="persist BIL-sell and QQQ-buy intents")
    entry.add_argument("events", type=Path)
    entry.add_argument("--trade-id", required=True)
    entry.add_argument("--signal-id", required=True)
    entry.add_argument("--entry-session", required=True)

    exit_cmd = sub.add_parser("exit-intents", help="persist QQQ-sell and BIL-buy intents")
    exit_cmd.add_argument("events", type=Path)
    exit_cmd.add_argument("--trade-id", required=True)
    exit_cmd.add_argument("--signal-id", required=True)
    exit_cmd.add_argument("--exit-session", required=True)
    exit_cmd.add_argument("--qqq-quantity", required=True, type=float)
    exit_cmd.add_argument("--estimated-proceeds", required=True, type=float)

    importer = sub.add_parser("import-fills", help="validate a normalized PAPER execution CSV")
    importer.add_argument("events", type=Path)
    importer.add_argument("csv", type=Path)
    reconciliation = sub.add_parser("reconcile-orders", help="import current/terminal status for PAPER orders")
    reconciliation.add_argument("events", type=Path)
    reconciliation.add_argument("csv", type=Path, help="one row per intent: PAPER account mode, broker order ID, requested quantity, status")

    preflight = sub.add_parser("preflight", help="validate and record a manual PAPER preflight checklist")
    preflight.add_argument("events", type=Path)
    preflight.add_argument("checklist", type=Path, help="privacy-safe checklist JSON; no account IDs or secrets")

    status = sub.add_parser("status", help="replay the event log and print reconciled holdings")
    status.add_argument("events", type=Path)

    nav = sub.add_parser("nav", help="mark ledger NAV and append an immutable daily record")
    nav.add_argument("events", type=Path)
    nav.add_argument("--date", required=True)
    nav.add_argument("--qqq-mark", required=True, type=float)
    nav.add_argument("--bil-mark", required=True, type=float)
    nav.add_argument("--qqq-source-hash", required=True)
    nav.add_argument("--bil-source-hash", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "seed":
            result = seed_event_log(
                args.events,
                session_date=args.date,
                initial_capital=args.initial_capital,
                bil_mark=args.bil_mark,
            )
        elif args.command == "entry-intents":
            result = append_order_intents(
                args.events,
                entry_intents(
                    trade_id=args.trade_id,
                    signal_id=args.signal_id,
                    entry_session=args.entry_session,
                ),
            )
        elif args.command == "exit-intents":
            result = append_order_intents(
                args.events,
                exit_intents(
                    trade_id=args.trade_id,
                    signal_id=args.signal_id,
                    exit_session=args.exit_session,
                    qqq_quantity=args.qqq_quantity,
                    estimated_proceeds=args.estimated_proceeds,
                ),
            )
        elif args.command == "import-fills":
            result = import_fill_csv_to_event_log(args.events, args.csv)
        elif args.command == "reconcile-orders":
            result = import_order_status_csv_to_event_log(args.events, args.csv)
        elif args.command == "preflight":
            checklist = json.loads(args.checklist.read_text(encoding="utf-8"))
            result = record_manual_preflight(args.events, checklist)
        elif args.command == "status":
            events = load_event_log(args.events)
            state = replay_event_log(events)
            result = {
                "account_mode": state["account_mode"],
                "initial_capital": state["initial_capital"],
                "cash": state["cash"],
                "qqq_units": state["qqq_units"],
                "bil_units": state["bil_units"],
                "cumulative_fees": state["cumulative_fees"],
                "cumulative_slippage_usd": state.get("cumulative_slippage_usd", 0.0),
                "execution_count": len(state["execution_ids"]),
                "event_count": len(events),
            }
        elif args.command == "nav":
            result = create_nav_from_event_log(
                args.events,
                session_date=args.date,
                qqq_mark=args.qqq_mark,
                bil_mark=args.bil_mark,
                source_hashes={"QQQ": args.qqq_source_hash, "BIL": args.bil_source_hash},
            )
        else:
            raise PaperProtocolError(f"unsupported command: {args.command}")
    except (PaperProtocolError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    _json(result if isinstance(result, dict) else {"events": result})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
