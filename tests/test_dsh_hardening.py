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


def test_no_reviewer_is_not_pass():
    r = run_review("diff", "task", cmd=None)
    assert r["status"] != "PASS"


def test_workflow_does_not_interpolate_inputs_in_shell():
    text = (ROOT / ".github/workflows/dsh-task.yml").read_text(encoding="utf-8")
    assert "--prompt \"${{ inputs.prompt }}\"" not in text
    assert "--task-id \"${{ inputs.task_id }}\"" not in text
    assert "TASK_PROMPT: ${{ inputs.prompt }}" in text
    assert "TASK_BRANCH: ${{ inputs.branch }}" in text
    assert "CODEX_CMD" not in text
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


def test_reviewer_timeout_is_blocked(tmp_path):
    script = tmp_path / "slow_review.py"
    script.write_text("import time; time.sleep(5)", encoding="utf-8")
    r = run_review("diff", "task", cmd=[sys.executable, str(script)], timeout=0.2)
    assert r["status"] == "BLOCKED"
    assert r["reason"] == "REVIEWER_TIMEOUT"


def test_task_timeout_persisted_not_running(tmp_path):
    from tools.automation.orchestrator import Orchestrator
    from tools.automation.state_store import TaskStore

    class TimeoutRunner:
        def run(self, prompt, log):
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text("timeout", encoding="utf-8")
            return {"returncode": 124, "final": None, "timed_out": True}

    store = TaskStore(tmp_path / "tasks.json")
    task = Orchestrator(store, TimeoutRunner(), repo=tmp_path, dry_run=True, require_protection=False).run_task("t-timeout", "p", "fix/t-timeout", "main")
    assert task["status"] in {"NEEDS_REVISION", "FAIL"}
    assert store.load()["tasks"]["t-timeout"]["status"] != "RUNNING"


def test_dsh_pr_flow_ends_review_pending_without_codex(tmp_path, monkeypatch):
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
            return subprocess.CompletedProcess(cmd, 0, "fix/t-pending", "")
        if cmd[:2] == ["git", "diff"]:
            return subprocess.CompletedProcess(cmd, 0, "diff", "")
        if cmd[:2] == ["gh", "pr"]:
            return subprocess.CompletedProcess(cmd, 0, "https://github.com/x/y/pull/1", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(mod, "run", fake_run)
    monkeypatch.setattr(mod, "changed_paths", lambda repo: ["docs/research/new.md"])
    monkeypatch.setattr(mod, "stage_allowed", lambda repo, paths: "diff")
    monkeypatch.setattr(mod, "commit_diff", lambda repo: "diff")
    store = TaskStore(tmp_path / "tasks.json")
    task = Orchestrator(store, FakeRunner(), repo=tmp_path, dry_run=False, require_protection=False).run_task("t-pending", "p", "fix/t-pending", "main")
    assert task["status"] == "REVIEW_PENDING"
    assert task["pr_url"].endswith("/pull/1")
    assert task["last_review"]["reviewer"] == "chatgpt"


def test_deployment_plan_targets_main_and_dispatch():
    doc = (ROOT / "docs/dsh/P0_1_4_DEPLOYMENT_BLOCKERS_AUDIT.md").read_text(encoding="utf-8")
    assert "DEPLOYMENT_PR_BASE: main" in doc
    assert "workflow_dispatch" in doc
    wf = (ROOT / ".github/workflows/dsh-task.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch" in wf
    assert "gh pr merge" not in wf
