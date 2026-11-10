# PAPER-50000 local state

`paper.sqlite` is the authoritative **local** PAPER-50000 account and ledger.
It is intentionally **not tracked by Git** and is excluded by `.gitignore`.
Do not delete or reset it to make a public page look populated.

Three distinct states:

| State | Where | Meaning |
|---|---|---|
| Code/test data | Git | Reproducible engine and fixtures |
| PAPER-50000 | local `data/paper_trading/paper.sqlite` | Persistent user paper account |
| Public snapshot | `dashboard/data/invest_terminal_data.json` | Read-only, redacted, no tokens |

GitHub Actions runs are ephemeral. If no persistent SQLite file is present, the
snapshot must say `LOCAL_PAPER_DB_NOT_PRESENT`; an Actions-created empty account
must not be presented as the user's real account.

Use the local API only through `http://127.0.0.1:8765/terminal.html`; it is
same-origin, session-authenticated and requires manual confirmation.
