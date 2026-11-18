import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def setup(tmp_path):
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
    store.update("t", status="PUBLISHING", agent_source_sha="a" * 40, base_commit_sha="b" * 40, artifact_digest="c" * 64, branch="fix/t", base_branch="main")
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


@pytest.mark.skipif(os.name == "nt", reason="POSIX git wrapper")
@pytest.mark.parametrize("case", ["malformed", "top_array", "tasks_missing", "task_missing", "identity", "bad_status", "pr_url_missing"])
def test_remote_json_negative(tmp_path, case):
    repo, store, bare = setup(tmp_path)

    def mutate(d):
        t = d.get("tasks", {}).get("t")
        if case == "malformed":
            d.clear()
            d["bad"] = True
        elif case == "top_array":
            d.clear(); d["tasks"] = []
        elif case == "tasks_missing":
            d.pop("tasks", None)
        elif case == "task_missing":
            d["tasks"].pop("t", None)
        elif case == "identity":
            t["artifact_digest"] = "d" * 64
        elif case == "bad_status":
            t["status"] = "UNKNOWN"
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
