import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

from tools.automation.headless import HeadlessRunner
from tools.automation.review import run_review
from tools.automation.validate import validate_base, validate_branch, validate_task_id

ROOT = Path(__file__).resolve().parents[1]


def test_malicious_identifiers_rejected():
    bad_ids = ["a b", "a;rm -rf /", "a$(id)", "a`id`", "a\nb", "-leading", "x" * 65]
    for value in bad_ids:
        with pytest.raises(ValueError):
            validate_task_id(value)
    bad_branches = ["main", "master", "feature/../main", "feature/a;id", "feature/a`id`", "feature/\nmain", "main"]
    for value in bad_branches:
        with pytest.raises(ValueError):
            validate_branch(value)
    with pytest.raises(ValueError):
        validate_base("feature/../main")


def test_valid_branches_and_base():
    assert validate_branch("fix/dsh-p0-1-hardening", "feature/dsh-headless-automation") == "fix/dsh-p0-1-hardening"
    assert validate_base("feature/dsh-headless-automation") == "feature/dsh-headless-automation"


def test_prompt_is_one_argument_not_shell(tmp_path):
    script = tmp_path / "argv.py"
    script.write_text("import json, sys; print(json.dumps({'type':'final','text':sys.argv[1]}))", encoding="utf-8")
    payload = "hello; rm -rf / $(id) `whoami`\nsecond line"
    out = HeadlessRunner([sys.executable, str(script)]).run(payload, tmp_path / "log.ndjson")
    assert out["returncode"] == 0
    assert out["final"] == payload


def test_headless_timeout_kills_child(tmp_path):
    script = tmp_path / "slow.py"
    script.write_text("import time; time.sleep(2); print('never')", encoding="utf-8")
    out = HeadlessRunner([sys.executable, str(script)], timeout=0.2).run("x", tmp_path / "log.ndjson")
    assert out["timed_out"] is True
    assert out["returncode"] == 124
    assert out["final"] is None


def test_headless_no_final_event(tmp_path):
    script = tmp_path / "nofinal.py"
    script.write_text("import json; print(json.dumps({'type':'session','sessionId':'s'}))", encoding="utf-8")
    out = HeadlessRunner([sys.executable, str(script)], timeout=2).run("x", tmp_path / "log.ndjson")
    assert out["final_event"] is False
    assert out["final"] is None


def test_reviewer_unavailable_is_blocked_not_pass():
    r = run_review("diff", "task", cmd=None)
    assert r["status"] == "BLOCKED"
    assert r["reason"] == "REVIEWER_UNAVAILABLE"


def test_workflow_does_not_interpolate_inputs_in_shell():
    text = (ROOT / ".github/workflows/dsh-task.yml").read_text(encoding="utf-8")
    assert "--prompt \"${{ inputs.prompt }}\"" not in text
    assert "--task-id \"${{ inputs.task_id }}\"" not in text
    assert "TASK_PROMPT: ${{ inputs.prompt }}" in text
    assert "TASK_BRANCH: ${{ inputs.branch }}" in text
    assert "git add automation/logs" not in text
    assert "gh pr merge" not in text
    wf = yaml.safe_load(text)
    assert "workflow_dispatch" in wf[True]


def test_pr_create_failure_is_terminal_fail(tmp_path, monkeypatch):
    import tools.automation.orchestrator as mod
    from tools.automation.orchestrator import Orchestrator
    from tools.automation.state_store import TaskStore

    class FakeRunner:
        def run(self, prompt, log):
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text('{"type":"final","text":"ok"}\n', encoding="utf-8")
            return {"returncode": 0, "final": "ok", "timed_out": False}

    def fake_run(cmd, cwd=None, check=True):
        if cmd[:2] == ["git", "rev-parse"]:
            return subprocess.CompletedProcess(cmd, 0, "fix/test", "")
        if cmd[:2] == ["git", "diff"]:
            return subprocess.CompletedProcess(cmd, 0, "diff", "")
        if cmd[:2] == ["gh", "pr"]:
            return subprocess.CompletedProcess(cmd, 1, "", "pr failed")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(mod, "run", fake_run)
    monkeypatch.setattr(mod, "changed_paths", lambda repo: ["docs/research/new.md"])
    monkeypatch.setattr(mod, "stage_allowed", lambda repo, paths: "diff")
    monkeypatch.setattr(mod, "commit_diff", lambda repo: "diff")
    store = TaskStore(tmp_path / "tasks.json")
    task = Orchestrator(store, FakeRunner(), repo=tmp_path, dry_run=False, require_protection=False).run_task("t4", "p", "fix/test", "feature/base")
    assert task["status"] == "FAIL"
    assert task["last_review"]["reason"] == "PR_CREATE_FAILED"
