# P0.2.13 Lock Adapter Design

LockPort + LockLease + fencing token. FakeLockBackend is deterministic. RedisLockAdapter uses SET NX PX and Lua owner/token/lease compare; client is injected and no real Redis was contacted. Real Redis connectivity: NOT_VERIFIED.
