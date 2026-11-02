# QQQ reversal paper implementation

The current implementation is broker-disconnected.

Implemented:
- SPY-calendar scheduling: next-session entry, exit five further SPY sessions after entry.
- Completed-close signal observations; stale or invalid data fail closed.
- Overlap suppression with a recorded reason.
- Separate BIL/QQQ entry and exit order-intent records.
- Fill import validation restricted to PAPER mode.
- Daily NAV marking and append-only JSONL events with duplicate-ID protection.

Not implemented:
- No market-data downloader or live feed.
- No IBKR API/TWS/Gateway connection, account selection, order submission, cancellation, or automation.
- No automatic conversion of order intents into orders.
- No broker statement parser or full cash/unit reconciliation.
- Running these helpers does not start the prospective observation clock.

Tests:
```bash
python -m pytest -q tests/test_qqq_transition_reversal_paper.py
```

A later phase must add a reviewed manual operator checklist, statement reconciliation, complete portfolio cash/unit accounting, and a dry run. A human must verify the Paper account in TWS before any manual test order. Never store credentials or account IDs in Git.
