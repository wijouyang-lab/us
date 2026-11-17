import json
import sys
from pathlib import Path

import yaml

from tools.automation.headless import HeadlessRunner
from tools.automation.orchestrator import Orchestrator
from tools.automation.review import run_review
from tools.automation.state_store import TaskStore, now

ROOT = Path(__file__).resolve().parents[1]


def test_task_state_recover_and_max_attempts(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    store.enqueue("t1", "do work", "automation/t1", max_attempts=2)
    task = store.claim("t1")
    assert task["status"] == "RUNNING" and task["attempts"] == 1
    assert store.recover_stale() == ["t1"]
    task = store.load()["tasks"]["t1"]
    assert task["status"] == "QUEUED"
    store.claim("t1")
    store.update("t1", status="RUNNING")
    store.recover_stale()
    assert store.load()["tasks"]["t1"]["status"] == "FAIL"


def test_orchestrator_dry_run_and_retry(tmp_path):
    class FakeRunner:
        def __init__(self): self.calls = []
        def run(self, prompt, log):
            self.calls.append(prompt)
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text('{"type":"final","text":"ok"}\n', encoding="utf-8")
            return {"returncode": 0, "final": "ok", "session_id": "s", "log": str(log)}

    store = TaskStore(tmp_path / "tasks.json")
    runner = FakeRunner()
    task = Orchestrator(store, runner, repo=tmp_path, dry_run=True).run_task("t2", "prompt", "automation/t2")
    assert task["status"] == "REVIEW_PENDING"
    assert runner.calls == ["prompt"]


def test_review_requires_independent_actor_and_never_self_approves():
    r = run_review("diff", "task", author="dsh", reviewer="dsh")
    assert r["status"] == "NEEDS_REVISION"
    assert r["reason"] == "SELF_REVIEW_FORBIDDEN"


def test_review_mock_closed_loop(tmp_path):
    script = tmp_path / "mock_codex.py"
    script.write_text("import json; print(json.dumps({'status':'PASS','reason':'OK','summary':'clean'}))", encoding="utf-8")
    r = run_review("diff", "task", cmd=[sys.executable, str(script)])
    assert r["status"] == "PASS"
    assert r["reason"] == "OK"


def test_headless_runner_parses_ndjson(tmp_path):
    script = tmp_path / "fake_dsh.py"
    script.write_text(
        "import json; print(json.dumps({'type':'session','sessionId':'s1'})); print(json.dumps({'type':'final','text':'DONE'}))",
        encoding="utf-8",
    )
    out = HeadlessRunner([sys.executable, str(script)]).run("prompt", tmp_path / "run.ndjson")
    assert out["returncode"] == 0
    assert out["session_id"] == "s1"
    assert out["final"] == "DONE"
    assert (tmp_path / "run.ndjson").exists()


def test_workflow_is_manual_only_and_has_no_merge():
    wf = yaml.safe_load((ROOT / ".github/workflows/dsh-task.yml").read_text(encoding="utf-8"))
    assert "workflow_dispatch" in wf[True]
    text = (ROOT / ".github/workflows/dsh-task.yml").read_text(encoding="utf-8")
    assert "gh pr merge" not in text
    assert "--draft" in text or "draft" in text.lower()
    assert "contents: write" in text
    assert "pull-requests: write" in text
    assert "timeout-minutes" in text


def test_repair_loop_stops_at_three(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    o = Orchestrator(store, object(), repo=tmp_path, dry_run=True)
    calls = []
    def fake(task_id, prompt, branch, base_branch="main"):
        calls.append(prompt)
        return {"status": "NEEDS_REVISION", "last_review": {"reason": "fix"}}
    o.run_task = fake
    result = o.run_with_repair("t3", "prompt", "automation/t3")
    assert len(calls) == 3
    assert result["status"] == "NEEDS_REVISION"
