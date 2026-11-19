import threading
from dataclasses import replace

import pytest

from tools.automation.lock_core import FakeClock, FakeLockAdapter, FakeLockBackend, LockError


def test_mutual_exclusion_and_key_scope():
    clock = FakeClock()
    backend = FakeLockBackend(clock)
    a = FakeLockAdapter(backend)
    b = FakeLockAdapter(backend)
    lease = a.acquire("branch", "task1", 10)
    with pytest.raises(LockError) as e:
        b.acquire("branch", "task2", 10)
    assert e.value.code == "LOCK_BUSY"
    assert b.acquire("other", "task2", 10).lock_key == "other"
    a.release(lease)
    assert b.acquire("branch", "task2", 10).fencing_token == 2


def test_owner_and_token_validation():
    adapter = FakeLockAdapter(FakeLockBackend(FakeClock()))
    lease = adapter.acquire("b", "a", 10)
    with pytest.raises(LockError):
        adapter.renew(replace(lease, owner_id="other"), 10)
    with pytest.raises(LockError):
        adapter.release(replace(lease, owner_id="other"))
    assert adapter.validate(lease)
    assert adapter.release(lease)


def test_expiry_and_fencing_old_owner():
    clock = FakeClock()
    adapter = FakeLockAdapter(FakeLockBackend(clock))
    old = adapter.acquire("b", "old", 5)
    clock.advance(6)
    new = adapter.acquire("b", "new", 5)
    assert new.fencing_token == old.fencing_token + 1
    with pytest.raises(LockError):
        adapter.renew(old, 5)
    with pytest.raises(LockError):
        adapter.release(old)
    assert adapter.validate(new)


def test_concurrent_acquire_one_winner():
    backend = FakeLockBackend()
    adapter = FakeLockAdapter(backend)
    barrier = threading.Barrier(8)
    results = []

    def worker(i):
        barrier.wait()
        try:
            results.append(("ok", adapter.acquire("shared", f"o{i}", 10)))
        except LockError as e:
            results.append(("busy", e.code))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(1 for r in results if r[0] == "ok") == 1
    assert sum(1 for r in results if r[0] == "busy") == 7
