import subprocess
import sys
from pathlib import Path

import pytest

from tools.automation.changes import changed_paths, commit_diff, stage_allowed, validate_paths
from tools.automation.headless import HeadlessRunner
from tools.automation.orchestrator import Orchestrator
from tools.automation.state_store import TaskStore


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def test_new_and_modified_files_are_staged_and_match_commit(tmp_path):
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "docs/research").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "docs/research/base.md").write_text("base", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "base")
    (tmp_path / "docs/research/new.md").write_text("new", encoding="utf-8")
    (tmp_path / "docs/research/base.md").write_text("changed", encoding="utf-8")
    (tmp_path / "tests/test_new.py").write_text("x=1\n", encoding="utf-8")
    paths = changed_paths(tmp_path)
    assert "docs/research/new.md" in paths
    staged = stage_allowed(tmp_path, paths)
    assert "new.md" in staged
    _git(tmp_path, "commit", "-m", "change")
    assert commit_diff(tmp_path) == staged


def test_unauthorized_path_is_blocked():
    with pytest.raises(ValueError, match="UNAUTHORIZED_PATH"):
        validate_paths(["main.py"])
    with pytest.raises(ValueError, match="UNAUTHORIZED_PATH"):
        validate_paths(["docs/research/../../main.py"])


def test_main_protection_unverified_blocks_real_run(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    o = Orchestrator(store, object(), repo=tmp_path, dry_run=False, require_protection=True)
    o.main_protected = lambda: False
    task = o.run_task("t-protect", "p", "fix/t-protect", "main")
    assert task["status"] == "BLOCKED"
    assert task["last_review"]["reason"] == "MAIN_PROTECTION_UNVERIFIED"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process-group semantics")
def test_child_process_group_is_killed(tmp_path):
    pidfile = tmp_path / "child.pid"
    parent = tmp_path / "parent.py"
    parent.write_text(
        "import subprocess,sys,time,pathlib\n"
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])\n"
        f"pathlib.Path({str(pidfile)!r}).write_text(str(child.pid))\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )
    out = HeadlessRunner([sys.executable, str(parent)], timeout=0.5).run("x", tmp_path / "log.ndjson")
    assert out["timed_out"] is True
    pid = int(pidfile.read_text())
    assert subprocess.run(["kill", "-0", str(pid)], capture_output=True).returncode != 0


def test_branch_switch_during_run_is_rejected(tmp_path):
    o = Orchestrator(TaskStore(tmp_path / "tasks.json"), object(), repo=tmp_path, dry_run=True)
    o._current_branch = lambda: "main"
    with pytest.raises(RuntimeError, match="BRANCH_GUARD"):
        o._assert_branch("fix/t")


def _repo(tmp_path):
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "docs/research").mkdir(parents=True)
    (tmp_path / "docs/research/in_allowed.md").write_text("a", encoding="utf-8")
    (tmp_path / "outside.py").write_text("m", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "base")
    return tmp_path


def test_rename_from_allowed_to_forbidden_is_blocked(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "mv", "docs/research/in_allowed.md", "outside2.py")
    paths = changed_paths(repo)
    assert "docs/research/in_allowed.md" in paths and "outside2.py" in paths
    with pytest.raises(ValueError, match="UNAUTHORIZED_PATH"):
        validate_paths(paths)


def test_rename_from_forbidden_to_allowed_is_blocked(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "mv", "outside.py", "docs/research/from_outside.md")
    paths = changed_paths(repo)
    assert "outside.py" in paths and "docs/research/from_outside.md" in paths
    with pytest.raises(ValueError, match="UNAUTHORIZED_PATH"):
        validate_paths(paths)


def test_staged_rename_keeps_both_paths(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "mv", "docs/research/in_allowed.md", "docs/research/renamed.md")
    _git(repo, "add", "-A")
    paths = changed_paths(repo)
    assert "docs/research/renamed.md" in paths and "docs/research/in_allowed.md" in paths
    validate_paths(paths)


def test_main_protection_api_three_states(monkeypatch, tmp_path):
    import subprocess
    import tools.automation.orchestrator as mod
    from tools.automation.orchestrator import Orchestrator
    from tools.automation.state_store import TaskStore

    o = Orchestrator(TaskStore(tmp_path / "tasks.json"), object(), repo=tmp_path, dry_run=True, require_protection=True)
    def fake(cmd, cwd=None, check=True):
        if cmd[:3] == ["gh", "repo", "view"]:
            return subprocess.CompletedProcess(cmd, 0, "o/r\n", "")
        if cmd[:2] == ["gh", "api"]:
            return subprocess.CompletedProcess(cmd, 0, {"true": "true\n", "false": "false\n"}.get(o._state, ""), "")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(mod, "run", fake)
    o._state = "true"; assert o.main_protected() is True
    o._state = "false"; assert o.main_protected() is False
    monkeypatch.setattr(mod, "run", lambda cmd, cwd=None, check=True: subprocess.CompletedProcess(cmd, 1, "", "denied"))
    assert o.main_protected() is False


def test_protection_blocked_task_resumes(tmp_path):
    from tools.automation.orchestrator import Orchestrator
    from tools.automation.state_store import TaskStore

    class FakeRunner:
        def run(self, prompt, log):
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text('{"type":"final","text":"ok"}\n', encoding="utf-8")
            return {"returncode": 0, "final": "ok", "timed_out": False}

    store = TaskStore(tmp_path / "tasks.json")
    store.enqueue("t-resume", "p", "fix/t-resume")
    store.update("t-resume", status="BLOCKED", last_review={"reason": "MAIN_PROTECTION_UNVERIFIED"})
    o = Orchestrator(store, FakeRunner(), repo=tmp_path, dry_run=True, require_protection=True)
    o.main_protected = lambda: True
    task = o.run_task("t-resume", "p", "fix/t-resume", "main")
    assert task["status"] == "REVIEW_PENDING"
    assert task["attempts"] == 1
    assert any(h["event"] == "resume_protection_blocked" for h in task["history"])


def test_non_protection_blocked_does_not_resume(tmp_path):
    from tools.automation.orchestrator import Orchestrator
    from tools.automation.state_store import TaskStore

    store = TaskStore(tmp_path / "tasks.json")
    store.enqueue("t-blocked", "p", "fix/t-blocked")
    store.update("t-blocked", status="BLOCKED", last_review={"reason": "PR_CREATE_FAILED"})
    o = Orchestrator(store, object(), repo=tmp_path, dry_run=True, require_protection=False)
    task = o.run_task("t-blocked", "p", "fix/t-blocked", "main")
    assert task["status"] == "BLOCKED"
