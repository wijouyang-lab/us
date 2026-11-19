from tools.automation.publisher_core import Pr, publish


class Git:
    def __init__(self, branch="fix/t", head="a" * 40, base="b" * 40):
        self.b, self.h, self.base = branch, head, base
        self.calls = []

    def head(self):
        self.calls.append("head")
        return self.h

    def branch(self):
        self.calls.append("branch")
        return self.b

    def base_sha(self, base):
        self.calls.append(("base", base))
        return self.base


class GH:
    def __init__(self, prs=None, create=True, fail_query=False, fail_create=False):
        self.prs = prs or []
        self.create = create
        self.fail_query = fail_query
        self.fail_create = fail_create
        self.calls = []

    def list_prs(self, head, base):
        self.calls.append(("list", head, base))
        if self.fail_query:
            raise RuntimeError("query")
        return self.prs

    def create_draft(self, head, base, task_id):
        self.calls.append(("create", head, base, task_id))
        if self.fail_create:
            raise RuntimeError("create")
        return "https://github.com/wijouyang-lab/us/pull/1"

    def get_pr(self, url):
        self.calls.append(("get", url))
        return Pr(url, True, "fix/t", "main")


class State:
    def __init__(self, task=None, fail=False):
        self.task_data = task
        self.fail = fail
        self.calls = []

    def task(self, task_id):
        self.calls.append(("task", task_id))
        return self.task_data

    def persist(self, task_id, **fields):
        self.calls.append(("persist", task_id, fields))
        return not self.fail


def manifest():
    return {"task_id": "t", "branch": "fix/t", "base_branch": "main", "source_commit_sha": "a" * 40, "base_commit_sha": "b" * 40}


def trusted():
    return {"task_id": "t", "branch": "fix/t", "base_branch": "main"}


def test_create_draft_with_fakes():
    gh, st = GH(), State()
    out = publish(manifest(), trusted(), Git(), gh, st)
    assert out["ok"] and out["pr_url"].endswith("/pull/1")
    assert gh.calls == [("list", "fix/t", "main"), ("create", "fix/t", "main", "t"), ("get", "https://github.com/wijouyang-lab/us/pull/1")]
    assert st.calls[-1][1] == "t"


def test_reuse_existing_draft():
    gh = GH([Pr("https://github.com/wijouyang-lab/us/pull/1", True, "fix/t", "main")])
    out = publish(manifest(), trusted(), Git(), gh, State())
    assert out["ok"] and out["skipped"] is False
    assert not any(c[0] == "create" for c in gh.calls)


def test_ready_and_multiple_blocked():
    ready = GH([Pr("u", False, "fix/t", "main")])
    assert publish(manifest(), trusted(), Git(), ready, State())["reason"] == "READY_PR_BLOCKED"
    multi = GH([Pr("u1", True, "fix/t", "main"), Pr("u2", True, "fix/t", "main")])
    assert publish(manifest(), trusted(), Git(), multi, State())["reason"] == "MULTIPLE_PR_BLOCKED"


def test_failures_and_state_failure():
    assert publish(manifest(), trusted(), Git(), GH(fail_query=True), State())["reason"] == "PR_QUERY_FAILED"
    assert publish(manifest(), trusted(), Git(), GH(fail_create=True), State())["reason"] == "PR_CREATE_FAILED"
    assert publish(manifest(), trusted(), Git(), GH(), State(fail=True))["reason"] == "STATE_PERSIST_FAILED"


def test_terminal_task_skipped():
    out = publish(manifest(), trusted(), Git(), GH(), State({"status": "REVIEW_PENDING", "pr_url": "u"}))
    assert out["ok"] and out["skipped"] is True

def test_publish_acquires_and_releases_lock():
    from tools.automation.lock_core import FakeClock, FakeLockAdapter, FakeLockBackend
    clock = FakeClock(); backend = FakeLockBackend(clock); lock = FakeLockAdapter(backend)
    out = publish(manifest(), trusted(), Git(), GH(), State(), lock)
    assert out["ok"] is True
    assert lock.acquire_calls == 1 and lock.release_calls == 1
    assert backend.acquire("fix/t", "other", 5).fencing_token == 2


def test_publish_lock_busy_fails_closed():
    from tools.automation.lock_core import FakeLockAdapter, FakeLockBackend, LockError
    class Busy:
        def acquire(self, *a): raise LockError("LOCK_BUSY")
        def validate(self, l): return True
        def release(self, l): return True
    out = publish(manifest(), trusted(), Git(), GH(), State(), Busy())
    assert out == {"ok": False, "reason": "LOCK_BUSY"}
