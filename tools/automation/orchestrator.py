"""DSH headless -> draft PR -> independent review state machine.

No merge operation exists in this module by design.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from tools.automation.review import run_review
from tools.automation.state_store import TaskStore


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=check)


class Orchestrator:
    def __init__(self, store: TaskStore, runner, repo: Path = Path("."), dry_run: bool = False):
        self.store = store
        self.runner = runner
        self.repo = Path(repo)
        self.dry_run = dry_run

    def _prepare_branch(self, branch: str) -> None:
        if self.dry_run:
            return
        current = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], self.repo).stdout.strip()
        if current != branch:
            run(["git", "fetch", "origin", "main"], self.repo, check=False)
            r = run(["git", "switch", branch], self.repo, check=False)
            if r.returncode != 0:
                run(["git", "switch", "-c", branch, "origin/main"], self.repo)

    def run_with_repair(self, task_id: str, prompt: str, branch: str) -> dict:
        task = None
        for _ in range(3):
            task = self.run_task(task_id, prompt, branch)
            if task["status"] in {"PASS", "FAIL", "REVIEW_PENDING"}:
                break
            review = task.get("last_review") or {}
            prompt = prompt + "\nReview feedback: " + str(review.get("reason", "NEEDS_REVISION"))
        return task

    def run_task(self, task_id: str, prompt: str, branch: str) -> dict:
        self.store.recover_stale()
        task = self.store.enqueue(task_id, prompt, branch)
        if task["attempts"] >= task["max_attempts"]:
            return self.store.update(task_id, status="FAIL", last_log="MAX_ATTEMPTS")
        task = self.store.claim(task_id)
        self._prepare_branch(branch)
        log = self.repo / "automation/logs" / f"{task_id}-attempt{task['attempts']}.ndjson"
        out = self.runner.run(prompt, log)
        if out["returncode"] != 0 or not out.get("final"):
            status = "NEEDS_REVISION" if task["attempts"] < task["max_attempts"] else "FAIL"
            return self.store.update(task_id, status=status, last_log=str(log), last_review={"reason": "HEADLESS_FAILED"})
        if self.dry_run:
            return self.store.update(task_id, status="REVIEW_PENDING", last_log=str(log), last_review={"reason": "DRY_RUN"})
        diff = run(["git", "diff", "--binary", "origin/main"], self.repo).stdout
        if not diff.strip():
            return self.store.update(task_id, status="FAIL", last_log=str(log), last_review={"reason": "EMPTY_DIFF"})
        for allowed in ("docs/research", "data/research", "tools/research", "tests"):
            if (self.repo / allowed).exists():
                run(["git", "add", allowed], self.repo)
        run(["git", "commit", "-m", f"automation: DSH task {task_id}"], self.repo)
        run(["git", "push", "-u", "origin", branch], self.repo)
        pr = run(["gh", "pr", "create", "--draft", "--base", "main", "--head", branch, "--title", f"DSH: {task_id}", "--body", f"Automated DSH task: {task_id}"], self.repo, check=False)
        pr_url = pr.stdout.strip().splitlines()[-1] if pr.stdout.strip() else ""
        review = run_review(diff, prompt, author="dsh", reviewer="codex")
        status = "PASS" if review["status"] == "PASS" else ("NEEDS_REVISION" if task["attempts"] < task["max_attempts"] else "FAIL")
        return self.store.update(task_id, status=status, pr_url=pr_url, last_log=str(log), last_review=review)
