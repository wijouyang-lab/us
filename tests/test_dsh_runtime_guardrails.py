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
