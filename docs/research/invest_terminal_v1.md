# Invest Terminal v1.1 — Security and Closed-Loop Status

Date: 2026-11-06
Branch: `research/invest-terminal-v1`
PR: #512 (Draft, not merged)
HEAD: `6a2afa26da45b1d8ef79387ee7ea4f0d768b82d2`

## v1.1 fixes

### Local API security

- Server binds **127.0.0.1 only**; no host/0.0.0.0 option.
- Serves `/terminal.html` and API from the **same origin**.
- Session cookie: `HttpOnly; SameSite=Strict`.
- Mutating requests require an `X-CSRF-Token` header.
- Exact Origin/Host checks; no wildcard CORS; `OPTIONS` fails closed.
- URL-controlled API base removed. The static page cannot be pointed at an
  arbitrary external API.
- Confirmation remains manual; proposals never auto-fill.

### Token redaction

- `build_snapshot()` removes `confirm_token`/`confirmation_token` and any
  credential-like keys recursively.
- Public orders are allowlisted fields only.
- A PENDING order test proves its live confirmation token does not appear in
  public JSON.
- The authenticated local `/api/session` may return pending confirmation info;
  it is never written to the public snapshot or artifact.

### SQLite

- `data/paper_trading/paper.sqlite` is no longer tracked.
- `.gitignore` excludes `*.sqlite`, WAL and SHM.
- Local DB was preserved (`git rm --cached` only).
- GitHub Actions no longer presents a fresh empty DB as the user's account;
  without a persistent DB the snapshot says `LOCAL_PAPER_DB_NOT_PRESENT`.

### Dashboard-to-terminal update

`dashboard-data.yml` now runs:

```bash
python -m tools.invest_terminal.build_snapshot
```

after a successful Dashboard refresh, before its existing `[skip ci]` commit.
The snapshot is included in the existing allowlist and commit.
If Dashboard refresh fails, the previous committed snapshot is not overwritten.
The existing `[skip ci]` commit prevents a self-trigger loop.

The workflow is main-only. It was not executed against main in this Draft branch;
the exact builder command and YAML guard are covered by tests, and the PR
workflow builds/uploads the read-only artifact without writing main.

## Local run

```bash
python -m tools.invest_terminal.build_snapshot
python -m tools.invest_terminal.server
# open the printed http://127.0.0.1:8765/terminal.html
```

The API is local paper only; static GitHub Pages remains read-only.

## Still blocked

All six style strategies remain `DATA_BLOCKED`; no PASS. P6.7 PIT gates still
fail, full-market scanner coverage is still only the Dashboard snapshot, and
current SPY/QQQ/BIL quotes are not in that snapshot. These are not represented as
returns or zeros.
