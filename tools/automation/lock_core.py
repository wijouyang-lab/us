"""LockPort protocol with deterministic fake backend and optional Redis adapter."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Callable, Protocol


class LockError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class LockLease:
    lock_key: str
    owner_id: str
    fencing_token: int
    acquired_at: float
    expires_at: float
    ttl_seconds: float
    lease_id: str


class LockPort(Protocol):
    def acquire(self, key: str, owner: str, ttl_seconds: float) -> LockLease: ...
    def renew(self, lease: LockLease, ttl_seconds: float) -> LockLease: ...
    def validate(self, lease: LockLease) -> bool: ...
    def release(self, lease: LockLease) -> bool: ...


class FakeClock:
    def __init__(self, now: float = 0.0):
        self.value = now

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class FakeLockBackend:
    def __init__(self, clock: Callable[[], float] | None = None):
        self.clock = clock or time.monotonic
        self._locks: dict[str, dict] = {}
        self._tokens: dict[str, int] = {}

    def acquire(self, key: str, owner: str, ttl_seconds: float) -> LockLease:
        now = self.clock()
        current = self._locks.get(key)
        if current and current["expires_at"] > now:
            raise LockError("LOCK_BUSY")
        token = self._tokens.get(key, 0) + 1
        self._tokens[key] = token
        lease = LockLease(key, owner, token, now, now + ttl_seconds, ttl_seconds, f"{key}:{token}")
        self._locks[key] = {"owner": owner, "token": token, "expires_at": lease.expires_at, "lease_id": lease.lease_id}
        return lease

    def validate(self, lease: LockLease) -> bool:
        cur = self._locks.get(lease.lock_key)
        return bool(cur and cur["owner"] == lease.owner_id and cur["token"] == lease.fencing_token and cur["lease_id"] == lease.lease_id and cur["expires_at"] > self.clock())

    def renew(self, lease: LockLease, ttl_seconds: float) -> LockLease:
        cur = self._locks.get(lease.lock_key)
        if not cur or cur["owner"] != lease.owner_id or cur["token"] != lease.fencing_token or cur["lease_id"] != lease.lease_id:
            raise LockError("LOCK_OWNER_MISMATCH")
        if cur["expires_at"] <= self.clock():
            raise LockError("LOCK_EXPIRED")
        expires = self.clock() + ttl_seconds
        cur["expires_at"] = expires
        return LockLease(lease.lock_key, lease.owner_id, lease.fencing_token, lease.acquired_at, expires, ttl_seconds, lease.lease_id)

    def release(self, lease: LockLease) -> bool:
        cur = self._locks.get(lease.lock_key)
        if not cur or cur["owner"] != lease.owner_id or cur["token"] != lease.fencing_token or cur["lease_id"] != lease.lease_id:
            raise LockError("LOCK_OWNER_MISMATCH")
        del self._locks[lease.lock_key]
        return True

    def acquire_for(self, key: str, owner: str, ttl_seconds: float) -> LockLease:
        return self.acquire(key, owner, ttl_seconds)


class FakeLockAdapter:
    def __init__(self, backend: FakeLockBackend | None = None):
        self.backend = backend or FakeLockBackend()
        self.acquire_calls = 0
        self.renew_calls = 0
        self.release_calls = 0

    def acquire(self, key, owner, ttl_seconds):
        self.acquire_calls += 1
        return self.backend.acquire(key, owner, ttl_seconds)

    def renew(self, lease, ttl_seconds):
        self.renew_calls += 1
        return self.backend.renew(lease, ttl_seconds)

    def validate(self, lease):
        return self.backend.validate(lease)

    def release(self, lease):
        self.release_calls += 1
        return self.backend.release(lease)


class RedisLockAdapter:
    """Redis SET NX PX + Lua compare-and-delete/renew; requires injected client."""

    ACQUIRE = """
    if redis.call('EXISTS', KEYS[1]) == 1 then return nil end
    local token = redis.call('INCR', KEYS[2])
    redis.call('SET', KEYS[1], ARGV[1] .. '|' .. token .. '|' .. ARGV[2], 'PX', ARGV[3])
    return token
    """
    RENEW = """
    local v = redis.call('GET', KEYS[1])
    if not v then return 0 end
    local owner, token, lease = string.match(v, '([^|]+)|([^|]+)|(.+)')
    if owner ~= ARGV[1] or token ~= ARGV[2] or lease ~= ARGV[3] then return 0 end
    redis.call('PEXPIRE', KEYS[1], ARGV[4])
    return 1
    """
    RELEASE = """
    local v = redis.call('GET', KEYS[1])
    if not v then return 0 end
    local owner, token, lease = string.match(v, '([^|]+)|([^|]+)|(.+)')
    if owner ~= ARGV[1] or token ~= ARGV[2] or lease ~= ARGV[3] then return 0 end
    redis.call('DEL', KEYS[1])
    return 1
    """

    def __init__(self, client, prefix: str = "dsh:lock:"):
        self.client = client
        self.prefix = prefix

    def acquire(self, key, owner, ttl_seconds):
        lock_key = self.prefix + key
        token_key = lock_key + ":token"
        import uuid
        lease_id = uuid.uuid4().hex
        token = self.client.eval(self.ACQUIRE, 2, lock_key, token_key, owner, lease_id, int(ttl_seconds * 1000))
        if not token:
            raise LockError("LOCK_BUSY")
        now = time.time()
        return LockLease(key, owner, int(token), now, now + ttl_seconds, ttl_seconds, lease_id)

    def renew(self, lease, ttl_seconds):
        lock_key = self.prefix + lease.lock_key
        ok = self.client.eval(self.RENEW, 1, lock_key, lease.owner_id, str(lease.fencing_token), lease.lease_id, int(ttl_seconds * 1000))
        if not ok:
            raise LockError("LOCK_LOST")
        return LockLease(lease.lock_key, lease.owner_id, lease.fencing_token, lease.acquired_at, time.time() + ttl_seconds, ttl_seconds, lease.lease_id)

    def validate(self, lease):
        lock_key = self.prefix + lease.lock_key
        v = self.client.get(lock_key)
        return isinstance(v, str) and v.split("|", 2) == [lease.owner_id, str(lease.fencing_token), lease.lease_id]

    def release(self, lease):
        lock_key = self.prefix + lease.lock_key
        ok = self.client.eval(self.RELEASE, 1, lock_key, lease.owner_id, str(lease.fencing_token), lease.lease_id)
        if not ok:
            raise LockError("LOCK_OWNER_MISMATCH")
        return True
