# Invest Terminal v1.1 — Acceptance Evidence

Date: 2026-11-06
Branch: `research/invest-terminal-v1`
PR: #512 (Draft)
HEAD: `6a2afa26da45b1d8ef79387ee7ea4f0d768b82d2`

## CI

- Full Test: **1428 passed, 1 skipped**
  https://github.com/wijouyang-lab/us/actions/runs/42171669802
- Invest Terminal Integration: success
  https://github.com/wijouyang-lab/us/actions/runs/42171669817
- Artifact: `invest-terminal-snapshot` (`13481322594`)

## v1.1 acceptance checklist

| # | Requirement | Evidence | Result |
|---|---|---|---|
| 1 | API loopback only | `serve()` fixed to `127.0.0.1`; static test rejects `ThreadingHTTPServer(("0.0.0.0"` | PASS |
| 2 | No wildcard CORS | server emits no `Access-Control-Allow-Origin`; `OPTIONS` returns 403 | PASS |
| 3 | Session auth | missing/wrong cookie returns 401; local page sets HttpOnly SameSite=Strict session | PASS |
| 4 | CSRF + Origin | no CSRF, bad Origin, cross-site `Sec-Fetch-Site` all return 403 | PASS |
| 5 | URL API forgery | no `?api=` / URL-controlled base in JS or HTML | PASS |
| 6 | Public snapshot token redaction | pending-order test asserts live `confirm_token` absent | PASS |
| 7 | SQLite untracked, local preserved | `git rm --cached`; local DB still exists with 50,000 cash / 0 orders | PASS |
| 8 | No fake Actions account | no-DB snapshot = `LOCAL_PAPER_DB_NOT_PRESENT`, NAV null | PASS |
| 9 | Local paper E2E | page GET → session → propose PENDING → positions unchanged → confirm → cash lower, 1 AAPL share, 1 ledger row | PASS |
| 10 | Dashboard → snapshot update | `dashboard-data.yml` builds snapshot before `[skip ci]` commit; YAML/command tested | PASS (main-only run not executed) |
| 11 | Workflow path bug | separate `tests/test_paper_trading_platform.py` and `tests/test_invest_terminal_server.py` paths | PASS |
| 12 | Frontend fallback | static snapshot first; local session only when available; no live-labeling | PASS |
| 13 | No auto-confirm | API returns PENDING; confirm requires explicit token; double confirm 400 | PASS |
| 14 | Full CI | 1428 passed, 1 skipped on final HEAD | PASS |

## E2E local request result

Automated HTTP test with a temporary SQLite account:

```text
GET /terminal.html                    200, HttpOnly session cookie
GET /api/session                      authenticated + CSRF
POST /api/paper/propose               PENDING
account positions                     []
POST /api/paper/confirm               200
account cash                          < 50,000
positions                             AAPL 1 share
ledger                                1 fill
second confirm                        400
GET /api/account                      no confirm token
```

The committed local DB was not modified by tests.

## Public snapshot states

- Local export with DB: `LOCAL_DB_EXPORT`, current cash/nav exported read-only.
- No persistent DB (CI/static build): `LOCAL_PAPER_DB_NOT_PRESENT`, NAV null.
- Neither state contains a confirmation token.

## Dashboard sync evidence

The exact command was run locally and by the PR integration workflow:

```bash
python -m tools.invest_terminal.build_snapshot
```

The PR workflow artifact shows the no-DB state (`LOCAL_PAPER_DB_NOT_PRESENT`,
NAV null). The main-only Dashboard commit path could not be run without merging
the Draft PR; its command, allowlist entry and `[skip ci]` loop guard are covered
by `tests/test_invest_terminal_snapshot_sync.py`.

## Remaining gaps

- Only one Dashboard-tracked stock; no full-market scanner surrogate.
- SPY/QQQ/BIL current quotes absent; benchmark status remains `DATA_BLOCKED`.
- No NAV history/closed trades, so no equity curve or attribution.
- P6.7 PIT gates still fail.
- Dividend remains issuer-level proxy only; options hedge remains blocked.
- All six strategies remain `DATA_BLOCKED`, not PASS.
