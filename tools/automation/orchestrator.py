"""DSH headless -> draft PR -> independent review state machine.

No merge operation exists in this module by design.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from tools.automation.review import run_review
from tools.automation.state_store import TaskStore
from tools.automation.validate import validate_base, validate_branch, validate_task_id


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=check)


class Orchestrator:
    def __init__(self, store: TaskStore, runner, repo: Path = Path("."), dry_run: bool = False):
        self.store = store
        self.runner = runner
        self.repo = Path(repo)
        self.dry_run = dry_run

    def _prepare_branch(self, branch: str, base_branch: str) -> None:
        if self.dry_run:
            return
        current = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], self.repo).stdout.strip()
        if current == branch:
            return
        if current in {"main", "master"}:
            run(["git", "fetch", "origin", base_branch], self.repo)
        r = run(["git", "switch", branch], self.repo, check=False)
        if r.returncode != 0:
            run(["git", "fetch", "origin", base_branch], self.repo)
            run(["git", "switch", "-c", branch, f"origin/{base_branch}"], self.repo)
        if run(["git", "rev-parse", "--abbrev-ref", "HEAD"], self.repo).stdout.strip() in {"main", "master"}:
            raise RuntimeError("REFUSE_TO_COMMIT_ON_MAIN")

    def run_with_repair(self, task_id: str, prompt: str, branch: str, base_branch: str = "main") -> dict:
        task = None
        for _ in range(3):
            task = self.run_task(task_id, prompt, branch, base_branch)
            if task["status"] in {"PASS", "FAIL", "BLOCKED", "REVIEW_PENDING"}:
                break
            review = task.get("last_review") or {}
            prompt = prompt + "\nReview feedback: " + str(review.get("reason", "NEEDS_REVISION"))
        return task

    def run_task(self, task_id: str, prompt: str, branch: str, base_branch: str = "main") -> dict:
        task_id = validate_task_id(task_id)
        branch = validate_branch(branch, base_branch)
        base_branch = validate_base(base_branch)
        self.store.recover_stale()
        task = self.store.enqueue(task_id, prompt, branch)
        if task["attempts"] >= task["max_attempts"]:
            return self.store.update(task_id, status="FAIL", last_log="MAX_ATTEMPTS")
        task = self.store.claim(task_id)
        self._prepare_branch(branch, base_branch)
        log = self.repo / "automation/logs" / f"{task_id}-attempt{task['attempts']}.ndjson"
        out = self.runner.run(prompt, log)
        if out["returncode"] != 0 or not out.get("final"):
            status = "NEEDS_REVISION" if task["attempts"] < task["max_attempts"] else "FAIL"
            return self.store.update(task_id, status=status, last_log=str(log), last_review={"reason": "HEADLESS_FAILED", "timed_out": out.get("timed_out", False)})
        if self.dry_run:
            return self.store.update(task_id, status="REVIEW_PENDING", last_log=str(log), last_review={"reason": "DRY_RUN"})
        diff = run(["git", "diff", "--binary", f"origin/{base_branch}"], self.repo).stdout
        if not diff.strip():
            return self.store.update(task_id, status="FAIL", last_log=str(log), last_review={"reason": "EMPTY_DIFF"})
        for allowed in ("docs/research", "data/research", "tools/research", "tests"):
            if (self.repo / allowed).exists():
                run(["git", "add", allowed], self.repo)
        run(["git", "commit", "-m", f"automation: DSH task {task_id}"], self.repo)
        run(["git", "push", "-u", "origin", branch], self.repo)
        task = self.store.load()["tasks"][task_id]
        if not task.get("pr_url"):
            pr = run(["gh", "pr", "create", "--draft", "--base", base_branch, "--head", branch, "--title", f"DSH: {task_id}", "--body", f"Automated DSH task: {task_id}"], self.repo, check=False)
            if pr.returncode != 0:
                return self.store.update(task_id, status="FAIL", last_log=str(log), last_review={"reason": "PR_CREATE_FAILED", "stderr": pr.stderr[-2000:]})
            pr_url = pr.stdout.strip().splitlines()[-1] if pr.stdout.strip() else ""
        else:
            pr_url = task["pr_url"]
        review = run_review(diff, prompt, author="dsh", reviewer="codex")
        if review["status"] == "BLOCKED":
            status = "BLOCKED"
        elif review["status"] == "PASS":
            status = "PASS"
        else:
            status = "NEEDS_REVISION" if task["attempts"] < task["max_attempts"] else "FAIL"
        return self.store.update(task_id, status=status, pr_url=pr_url, last_log=str(log), last_review=review)
