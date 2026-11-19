import threading
from dataclasses import replace

from tools.automation.lock_core import FakeLockAdapter, FakeLockBackend, LockError, LockLease
from tools.automation.publisher_core import publish


class C:
    def __init__(self): self.calls=[]
    def head(self): self.calls.append("head"); return "a"*40
    def branch(self): self.calls.append("branch"); return "fix/t"
    def base_sha(self, b): self.calls.append("base"); return "b"*40

class G:
    def __init__(self): self.calls=[]
    def list_prs(self,*a): self.calls.append("list"); return []
    def create_draft(self,*a): self.calls.append("create"); return "https://github.com/wijouyang-lab/us/pull/1"
    def get_pr(self,u): self.calls.append("get"); from tools.automation.publisher_core import Pr; return Pr(u,True,"fix/t","main")

class S:
    def __init__(self): self.calls=[]; self.data=None
    def task(self,t): self.calls.append("task"); return self.data
    def persist(self,*a,**k): self.calls.append("persist"); return True

def m(): return {"task_id":"t","branch":"fix/t","base_branch":"main","source_commit_sha":"a"*40,"base_commit_sha":"b"*40}
def tr(): return {"task_id":"t","branch":"fix/t","base_branch":"main"}

def test_lock_none_fails_before_any_side_effect():
    g,s=C(),S(); out=publish(m(),tr(),C(),g,s,None)
    assert out["reason"]=="LOCK_NOT_CONFIGURED"
    assert g.calls==[] and s.calls==[]

def test_invalid_lease_rejected():
    class L:
        def acquire(self,*a): return LockLease("wrong","t",0,0,0,0,"")
        def release(self,l): return True
        def validate(self,l): return True
    g,s=G(),S(); out=publish(m(),tr(),C(),g,s,L())
    assert out["reason"]=="INVALID_LEASE"
    assert g.calls==[] and s.calls==[]

def test_early_return_releases_lock():
    lock=FakeLockAdapter(FakeLockBackend())
    class BadState(S):
        pass
    out=publish({**m(),"task_id":"x"},tr(),C(),G(),S(),lock)
    assert out["reason"]=="MANIFEST_INPUT_MISMATCH"
    assert lock.acquire_calls==1 and lock.release_calls==1

def test_lock_lost_before_create_blocks_side_effect():
    backend=FakeLockBackend(); lock=FakeLockAdapter(backend)
    class Expire(FakeLockAdapter):
        def validate(self, lease): return False
    g=G(); out=publish(m(),tr(),C(),g,S(),Expire(backend))
    assert out["reason"]=="LOCK_LOST"
    assert "create" not in g.calls

def test_release_failure_not_success():
    class L:
        def acquire(self,k,o,t): return LockLease(k,o,1,0,t,t,"x")
        def validate(self,l): return True
        def release(self,l): raise LockError("LOCK_RELEASE_FAILED")
    out=publish(m(),tr(),C(),G(),S(),L())
    assert out["ok"] is False and out["reason"]=="LOCK_RELEASE_FAILED"

def test_100_thread_atomic_acquire():
    b=FakeLockBackend(); a=FakeLockAdapter(b); barrier=threading.Barrier(100); res=[]
    def w(i):
        barrier.wait()
        try: a.acquire("branch:main",f"o{i}",10); res.append("ok")
        except LockError: res.append("busy")
    ts=[threading.Thread(target=w,args=(i,)) for i in range(100)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert res.count("ok")==1 and res.count("busy")==99
