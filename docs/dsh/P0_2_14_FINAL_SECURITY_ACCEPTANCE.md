# P0.2.14: Lock Mandatory Enforcement and Lease Lifecycle Audit

Date: 2026-11-19
Branch: `deploy/dsh-automation-p0`
CODE HEAD: `aed0b3c7ce53d2b528d896a0a369e9f7d535484b`
Base main: `1a5f0bd69d236eada0da5fd186c8d5188bbab08c`

## Fixed

- `publisher_core.publish()` no longer has `lock=None` success path:
  `LOCK_NOT_CONFIGURED` returns before any Git/GitHub/state call.
- Lease is validated immediately after acquire, before PR create, after PR
  create, and before state persist.
- All early-return paths go through a single `finish()` release; failed release
  adds `cleanup_state=FAILED` and `reason=LOCK_RELEASE_FAILED` (never success).
- Invalid lease (wrong key/owner/token/TTL/id) returns `INVALID_LEASE`.
- PR create followed by lock loss records `publication_state=PR_CREATED` and
  `reason=LOCK_LOST` instead of pretending no side effect.

## Tests

`tests/test_publisher_lock_safety.py`:

- lock=None before side effects;
- invalid lease rejected with zero GitHub calls;
- early-return release;
- lock lost before create -> no create call;
- release failure not success;
- 100-thread atomic acquire (1 winner / 99 busy).

`tests/test_publisher_adapters.py` updated with mandatory lock; all existing
PR/recovery cases pass.

## Still partial / blocked

- FakeLockBackend uses Python dict with GIL-only atomicity; explicit `RLock`
  patch was not applied. `FAKE_BACKEND_ATOMIC_ACQUIRE: PARTIAL`.
- Redis adapter validation/bytes/Cluster hash tag changes were NOT applied in
  this round. `REDIS_ADAPTER_HARDENING: BLOCKED/PARTIAL`.
- Real Redis integration: NOT_VERIFIED.
- Production `_publish_main` remains legacy; production `main()` still returns
  `BLOCKED:LOCK_NOT_IMPLEMENTED`.
- Windows taskkill failure, reader timeout, Python hashes, full DSH spawn remain
  PARTIAL/BLOCKED.

## CI

Final code CI must be checked at the final HEAD; this document is committed
after code. CI URL: pending final run.
