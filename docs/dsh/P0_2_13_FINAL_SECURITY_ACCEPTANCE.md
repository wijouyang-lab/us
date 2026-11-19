# P0.2.13: Publisher Distributed Lock and Concurrency Audit

Date: 2026-11-19
Branch: `deploy/dsh-automation-p0`
HEAD: `3baaae322f53b906030098e001eda14a46ae66c8`
Base main: `42d3a19ee205713fdfa9d959ff04d1fd79d3b65b`

## 1. Lock core

`tools/automation/lock_core.py` adds:

- `LockLease` (key, owner, fencing token, times, TTL, lease id);
- `LockPort` protocol: acquire/renew/validate/release;
- explicit `LockError` codes (`LOCK_BUSY`, `LOCK_OWNER_MISMATCH`,
  `LOCK_EXPIRED`, `LOCK_LOST`, etc.);
- deterministic `FakeClock` and `FakeLockBackend` with monotonic fencing tokens;
- `FakeLockAdapter` with call counters;
- `RedisLockAdapter` using SET NX PX and Lua compare/renew/release, with
  injected client only.

Tests: `tests/test_lock_core.py`, including 5/10/20-thread contention
(one winner, n-1 busy), owner mismatch, expiry/fencing, old-owner rejection.

## 2. Publisher core

`publisher_core.publish(..., lock=None)` acquires a branch lock, validates the
lease before state persistence, and releases with explicit
`LOCK_RELEASE_FAILED` distinction. Fake lock tests cover acquire/release and
LOCK_BUSY fail-closed.

Production `publisher.main()` remains OIDC-gated and then
`BLOCKED:LOCK_NOT_IMPLEMENTED`; legacy `_publish_main` is not yet wired to the
Adapter core. `PRODUCTION_ADAPTER_WIRING` remains PARTIAL.

## 3. Infrastructure

No real Redis service/password is configured or read.
`REAL_REDIS_CONNECTIVITY: NOT_VERIFIED`;
`PRODUCTION_SHARED_LOCK: BLOCKED`.

GitHub Actions concurrency (`dsh-task-${branch}`, queue max) is only a
scheduling gate, not the authoritative distributed lock.

## 4. Remaining gaps

- production Publisher still blocked;
- real Redis lock not verified;
- Windows taskkill failure paths PARTIAL;
- reader blocked-timeout PARTIAL;
- Python hash lock BLOCKED;
- full DSH service spawn PARTIAL.

## 5. CI

Full CI before final doc: **1522 passed, 1 skipped, 0 xfailed**.
Jobs: test, dsh-install-verify, dsh-subprocess-isolation,
dsh-process-cleanup-windows all success.
