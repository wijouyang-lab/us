import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def setup(tmp_path, extra=None):
    from tools.automation.state_store import TaskStore
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
    repo = tmp_path / "a"
    subprocess.run(["git", "clone", str(bare), str(repo)], check=True, capture_output=True)
    for key, value in (("user.email", "t@example.com"), ("user.name", "t")):
        subprocess.run(["git", "config", key, value], cwd=repo, check=True)
    (repo / "automation/state").mkdir(parents=True)
    (repo / "base.txt").write_text("base", encoding="utf-8")
    store = TaskStore(repo / "automation/state/tasks.json")
    store.enqueue("t", "prompt", "fix/t")
    fields = {"status": "PUBLISHING", "agent_source_sha": "a" * 40, "base_commit_sha": "b" * 40, "artifact_digest": "c" * 64, "branch": "fix/t", "base_branch": "main"}
    if extra:
        fields.update(extra)
    store.update("t", **fields)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo, check=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=repo, check=True)
    subprocess.run(["git", "switch", "-c", "fix/t"], cwd=repo, check=True)
    subprocess.run(["git", "push", "-u", "origin", "fix/t"], cwd=repo, check=True)
    return repo, store, bare


def advance(bare, tmp_path, mutate):
    b = tmp_path / "b"
    subprocess.run(["git", "clone", "-b", "fix/t", str(bare), str(b)], check=True, capture_output=True)
    for key, value in (("user.email", "t@example.com"), ("user.name", "t")):
        subprocess.run(["git", "config", key, value], cwd=b, check=True)
    p = b / "automation/state/tasks.json"
    data = json.loads(p.read_text())
    mutate(data)
    p.write_text(json.dumps(data), encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=b, check=True)
    subprocess.run(["git", "commit", "-m", "automation: persist task state [skip ci]"], cwd=b, check=True)
    subprocess.run(["git", "push", "origin", "fix/t"], cwd=b, check=True)


def wrapper(tmp_path):
    d = tmp_path / "bin"; d.mkdir()
    s = d / "git"
    s.write_text("#!/bin/sh\nfor a in \"$@\"; do if [ \"$a\" = push ]; then /usr/bin/git \"$@\"; exit 1; fi; done\nexec /usr/bin/git \"$@\"\n", encoding="utf-8")
    s.chmod(0o755)
    return d


def call(repo, store, bin_dir):
    from tools.automation.publisher import push_state
    old = os.environ["PATH"]
    os.environ["PATH"] = f"{bin_dir}:{old}"
    try:
        return push_state(store, repo, "fix/t", "t", force_remote_check=True)
    finally:
        os.environ["PATH"] = old


@pytest.mark.skipif(os.name == "nt", reason="POSIX git wrapper")
def test_state_push_client_error_remote_advanced_contains_commit(tmp_path):
    repo, store, bare = setup(tmp_path)
    def _advance_state(d):
        d["tasks"]["t"]["last_review"] = {"reason": "advanced"}
    advance(bare, tmp_path, _advance_state)
    assert call(repo, store, wrapper(tmp_path)) is True


NEGATIVE_CASES = [
    "malformed", "top_array", "tasks_missing", "task_missing", "task_id_mismatch", "task_id_missing",
    "identity", "source", "base", "branch", "base_branch", "bad_status",
    "rollback", "published_deleted", "published_replaced", "published_format",
    "published_missing", "pr_url_replaced", "pr_url_format", "pr_url_missing",
]


@pytest.mark.skipif(os.name == "nt", reason="POSIX git wrapper")
@pytest.mark.parametrize("case", NEGATIVE_CASES)
def test_remote_json_negative(tmp_path, case):
    extra = {}
    if case in {"published_deleted", "published_replaced"}:
        extra["published_sha"] = "d" * 40
    if case == "rollback":
        extra.update(status="REVIEW_PENDING", pr_url="https://github.com/wijouyang-lab/us/pull/1")
    if case == "pr_url_replaced":
        extra["pr_url"] = "https://github.com/wijouyang-lab/us/pull/1"
    repo, store, bare = setup(tmp_path, extra)

    def mutate(d):
        t = d.get("tasks", {}).get("t")
        if case == "malformed":
            d.clear(); d["bad"] = True
        elif case == "top_array":
            d.clear(); d["tasks"] = []
        elif case == "tasks_missing":
            d.pop("tasks", None)
        elif case == "task_missing":
            d["tasks"].pop("t", None)
        elif case == "task_id_mismatch":
            t["task_id"] = "other"
        elif case == "task_id_missing":
            t.pop("task_id", None)
        elif case == "identity":
            t["artifact_digest"] = "d" * 64
        elif case == "source":
            t["agent_source_sha"] = "e" * 40
        elif case == "base":
            t["base_commit_sha"] = "e" * 40
        elif case == "branch":
            t["branch"] = "fix/other"
        elif case == "base_branch":
            t["base_branch"] = "release"
        elif case == "bad_status":
            t["status"] = "UNKNOWN"
        elif case == "rollback":
            t["status"] = "PUBLISHING"
        elif case == "published_deleted":
            t.pop("published_sha", None)
        elif case == "published_replaced":
            t["published_sha"] = "e" * 40
        elif case == "published_format":
            t["published_sha"] = "bad"
        elif case == "published_missing":
            t["published_sha"] = "e" * 40
        elif case == "pr_url_replaced":
            t["pr_url"] = "https://github.com/wijouyang-lab/us/pull/2"
        elif case == "pr_url_format":
            t["pr_url"] = "not-a-url"
        elif case == "pr_url_missing":
            t["status"] = "REVIEW_PENDING"; t.pop("pr_url", None)
        else:
            raise AssertionError(case)

    if case == "malformed":
        b = tmp_path / "b"
        subprocess.run(["git", "clone", "-b", "fix/t", str(bare), str(b)], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=b, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=b, check=True)
        (b / "automation/state/tasks.json").write_text("{not json", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=b, check=True)
        subprocess.run(["git", "commit", "-m", "automation: persist task state [skip ci]"], cwd=b, check=True)
        subprocess.run(["git", "push", "origin", "fix/t"], cwd=b, check=True)
    else:
        advance(bare, tmp_path, mutate)
    assert call(repo, store, wrapper(tmp_path)) is False


def fail_wrapper(tmp_path, command):
    d = tmp_path / "failbin"; d.mkdir()
    s = d / "git"
    s.write_text(f"""#!/bin/sh
for a in "$@"; do
  if [ "$a" = "{command}" ]; then exit 1; fi
  if [ "$a" = push ]; then /usr/bin/git "$@"; exit 1; fi
done
exec /usr/bin/git "$@"
""", encoding="utf-8")
    s.chmod(0o755)
    return d


@pytest.mark.skipif(os.name == "nt", reason="POSIX git wrapper")
@pytest.mark.parametrize("command", ["fetch", "show", "rev-list", "merge-base"])
def test_git_command_failure_closed(tmp_path, command):
    repo, store, bare = setup(tmp_path)

    def _advance_state(d):
        d["tasks"]["t"]["last_review"] = {"reason": "advanced"}

    advance(bare, tmp_path, _advance_state)
    assert call(repo, store, fail_wrapper(tmp_path, command)) is False


@pytest.mark.skipif(os.name == "nt", reason="POSIX git wrapper")
def test_cat_file_failure_closed(tmp_path):
    repo, store, bare = setup(tmp_path)
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    store.update("t", published_sha=base)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "automation: persist task state [skip ci]"], cwd=repo, check=True)
    subprocess.run(["git", "push", "origin", "fix/t"], cwd=repo, check=True)
    advance(bare, tmp_path, lambda d: d["tasks"]["t"].update({"published_sha": base}))
    assert call(repo, store, fail_wrapper(tmp_path, "cat-file")) is False


def clone_b(bare, tmp_path):
    b = tmp_path / "b_extra"
    subprocess.run(["git", "clone", "-b", "fix/t", str(bare), str(b)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=b, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=b, check=True)
    return b


@pytest.mark.skipif(os.name == "nt", reason="POSIX git wrapper")
def test_published_sha_object_exists_but_not_in_history(tmp_path):
    repo, store, bare = setup(tmp_path)
    orphan = subprocess.check_output(["git", "commit-tree", "HEAD^{tree}", "-m", "orphan"], cwd=repo, text=True).strip()
    store.update("t", published_sha=orphan)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "automation: persist task state [skip ci]"], cwd=repo, check=True)
    subprocess.run(["git", "push", "origin", "fix/t"], cwd=repo, check=True)
    assert subprocess.run(["git", "cat-file", "-e", f"{orphan}^{{commit}}"], cwd=repo).returncode == 0
    b = clone_b(bare, tmp_path)
    p = b / "automation/state/tasks.json"
    d = json.loads(p.read_text()); d["tasks"]["t"]["last_review"] = {"reason": "advanced"}
    p.write_text(json.dumps(d), encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=b, check=True)
    subprocess.run(["git", "commit", "-m", "automation: persist task state [skip ci]"], cwd=b, check=True)
    subprocess.run(["git", "push", "origin", "fix/t"], cwd=b, check=True)
    assert call(repo, store, wrapper(tmp_path)) is False


def add_followup(b, kind):
    if kind == "valid":
        return
    if kind == "empty":
        subprocess.run(["git", "commit", "--allow-empty", "-m", "automation: persist task state [skip ci]"], cwd=b, check=True)
    elif kind == "nonstate":
        (b / "bad.txt").write_text("bad", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=b, check=True)
        subprocess.run(["git", "commit", "-m", "automation: persist task state [skip ci]"], cwd=b, check=True)
    elif kind == "bad_subject":
        (b / "automation/state/tasks.json").write_text("{}", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=b, check=True)
        subprocess.run(["git", "commit", "-m", "human change"], cwd=b, check=True)
    elif kind == "transient":
        (b / "bad.txt").write_text("bad", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=b, check=True)
        subprocess.run(["git", "commit", "-m", "automation: persist task state [skip ci]"], cwd=b, check=True)
        (b / "bad.txt").unlink()
        subprocess.run(["git", "add", "."], cwd=b, check=True)
        subprocess.run(["git", "commit", "-m", "automation: persist task state [skip ci]"], cwd=b, check=True)
    elif kind == "merge":
        subprocess.run(["git", "switch", "-c", "side"], cwd=b, check=True)
        (b / "side.txt").write_text("side", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=b, check=True)
        subprocess.run(["git", "commit", "-m", "automation: persist task state [skip ci]"], cwd=b, check=True)
        subprocess.run(["git", "switch", "fix/t"], cwd=b, check=True)
        subprocess.run(["git", "merge", "--no-ff", "side", "-m", "automation: persist task state [skip ci]"], cwd=b, check=True)
    elif kind == "rename":
        subprocess.run(["git", "mv", "automation/state/tasks.json", "automation/state/other.json"], cwd=b, check=True)
        subprocess.run(["git", "commit", "-m", "automation: persist task state [skip ci]"], cwd=b, check=True)
    elif kind == "copy":
        (b / "automation/state/source.json").write_text("{\"copy\": true}\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=b, check=True)
        subprocess.run(["git", "commit", "-m", "automation: persist task state [skip ci]"], cwd=b, check=True)
        shutil.copy2(b / "automation/state/source.json", b / "automation/state/copied.json")
        subprocess.run(["git", "add", "."], cwd=b, check=True)
        subprocess.run(["git", "commit", "-m", "automation: persist task state [skip ci]"], cwd=b, check=True)
        raw = subprocess.check_output(["git", "diff-tree", "--no-commit-id", "--name-status", "-r", "-M", "-C", "--find-copies-harder", "HEAD~1", "HEAD"], cwd=b, text=True)
        rows = [line.split("\t") for line in raw.splitlines() if line.strip()]
        assert any(row and row[0].startswith("C") for row in rows), raw


@pytest.mark.skipif(os.name == "nt", reason="POSIX git wrapper")
@pytest.mark.parametrize("kind,expected", [("valid", True), ("empty", False), ("nonstate", False), ("bad_subject", False), ("transient", False), ("merge", False), ("rename", False), ("copy", False)])
def test_remote_advanced_followup_commit_checks(tmp_path, kind, expected):
    repo, store, bare = setup(tmp_path)
    b = clone_b(bare, tmp_path)
    add_followup(b, kind)
    subprocess.run(["git", "push", "origin", "fix/t"], cwd=b, check=True)
    assert call(repo, store, wrapper(tmp_path)) is expected


@pytest.mark.skipif(os.name == "nt", reason="POSIX git wrapper")
def test_remote_advanced_fork_history_rejected(tmp_path):
    repo, store, bare = setup(tmp_path)
    store.update("t", last_review={"reason": "local"})
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "automation: persist task state [skip ci]"], cwd=repo, check=True)
    b = clone_b(bare, tmp_path)
    p = b / "automation/state/tasks.json"
    d = json.loads(p.read_text()); d["tasks"]["t"]["last_review"] = {"reason": "remote"}
    p.write_text(json.dumps(d), encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=b, check=True)
    subprocess.run(["git", "commit", "-m", "automation: persist task state [skip ci]"], cwd=b, check=True)
    subprocess.run(["git", "push", "origin", "fix/t"], cwd=b, check=True)
    assert call(repo, store, wrapper(tmp_path)) is False
