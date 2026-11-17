import subprocess
from pathlib import Path

import pytest

from tools.automation.publisher import recovery_range_ok, state_only_ok


def g(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, text=True, capture_output=True).stdout.strip()


def repo(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    g(tmp_path, "config", "user.email", "t@example.com")
    g(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    g(tmp_path, "add", ".")
    g(tmp_path, "commit", "-m", "base")
    return tmp_path


def commit(repo, path, text, message):
    p = repo / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    g(repo, "add", ".")
    g(repo, "commit", "-m", message)
    return g(repo, "rev-parse", "HEAD")


def test_recovery_allows_expected_state_commits(tmp_path):
    r = repo(tmp_path)
    source = g(r, "rev-parse", "HEAD")
    code = commit(r, "docs/research/x.md", "x", "automation: DSH task t artifact abc")
    state = commit(r, "automation/state/tasks.json", "{}", "automation: persist task state [skip ci]")
    assert recovery_range_ok(r, code, state) is True
    assert state_only_ok(r, source, state) is False


def test_recovery_blocks_unknown_commit_after_artifact(tmp_path):
    r = repo(tmp_path)
    code = commit(r, "docs/research/x.md", "x", "automation: DSH task t artifact abc")
    head = commit(r, "docs/research/y.md", "y", "human change")
    assert recovery_range_ok(r, code, head) is False


def test_recovery_rejects_unrecognized_file_changes(tmp_path):
    r = repo(tmp_path)
    code = commit(r, "docs/research/x.md", "x", "automation: DSH task t artifact abc")
    head = commit(r, "automation/state/tasks.json", "{}", "automation: persist task state [skip ci]")
    # A state commit followed by a non-state change is rejected.
    bad = commit(r, "docs/research/human.md", "z", "automation: persist task state [skip ci]")
    assert recovery_range_ok(r, code, head) is True
    assert recovery_range_ok(r, code, bad) is False


def test_recovery_rejects_unexpected_merge_commit(tmp_path):
    r = repo(tmp_path)
    code = commit(r, "docs/research/x.md", "x", "automation: DSH task t artifact abc")
    g(r, "switch", "-c", "side")
    commit(r, "side.txt", "s", "side")
    g(r, "switch", "master")
    g(r, "merge", "--no-ff", "side", "-m", "automation: persist task state [skip ci]")
    head = g(r, "rev-parse", "HEAD")
    assert recovery_range_ok(r, code, head) is False
