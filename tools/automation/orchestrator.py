"""DSH headless -> staged diff -> draft PR -> independent review.

No merge operation exists in this module by design.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from tools.automation.changes import changed_paths, commit_diff, stage_allowed, validate_paths
from tools.automation.state_store import TaskStore
from tools.automation.validate import validate_base, validate_branch, validate_task_id


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=check)


class Orchestrator:
    def __init__(self, store: TaskStore, runner, repo: Path = Path("."), dry_run: bool = False, require_protection: bool = True):
        self.store = store
        self.runner = runner
        self.repo = Path(repo)
        self.dry_run = dry_run
        self.require_protection = require_protection

    def _current_branch(self) -> str:
        return run(["git", "rev-parse", "--abbrev-ref", "HEAD"], self.repo).stdout.strip()

    def _assert_branch(self, branch: str) -> None:
        current = self._current_branch()
        if current in {"main", "master"} or current != branch:
            raise RuntimeError(f"BRANCH_GUARD:{current}")

    def _prepare_branch(self, branch: str, base_branch: str) -> None:
        if self.dry_run:
            return
        current = self._current_branch()
        if current == branch:
            return
        run(["git", "fetch", "origin", base_branch], self.repo, check=False)
        r = run(["git", "switch", branch], self.repo, check=False)
        if r.returncode != 0:
            run(["git", "switch", "-c", branch, f"origin/{base_branch}"], self.repo)
        self._assert_branch(branch)

    def main_protected(self) -> bool:
        slug = run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"], self.repo, check=False)
        if slug.returncode != 0 or not slug.stdout.strip():
            return False
        r = run(["gh", "api", f"repos/{slug.stdout.strip()}/branches/main", "--jq", ".protected"], self.repo, check=False)
        if r.returncode != 0 or not r.stdout.strip():
            return False
        return r.stdout.strip().lower() == "true"

    def _status(self, task_id: str, status: str, **fields) -> dict:
        return self.store.update(task_id, status=status, **fields)

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
        try:
            task_id = validate_task_id(task_id)
            base_branch = validate_base(base_branch)
            branch = validate_branch(branch, base_branch)
        except ValueError as e:
            return {"status": "BLOCKED", "reason": str(e)}
        self.store.recover_stale()
        task = self.store.enqueue(task_id, prompt, branch)
        if task["status"] == "BLOCKED":
            if (task.get("last_review") or {}).get("reason") != "MAIN_PROTECTION_UNVERIFIED":
                return task
            if self.require_protection and not self.dry_run and not self.main_protected():
                return task
            self.store.resume_protection_blocked(task_id)
            task = self.store.load()["tasks"][task_id]
        if task["attempts"] >= task["max_attempts"]:
            return self._status(task_id, "FAIL", last_log="MAX_ATTEMPTS")
        if not self.dry_run and self.require_protection and not self.main_protected():
            return self._status(task_id, "BLOCKED", last_review={"reason": "MAIN_PROTECTION_UNVERIFIED"})
        task = self.store.claim(task_id)
        try:
            self._prepare_branch(branch, base_branch)
        except RuntimeError as e:
            return self._status(task_id, "BLOCKED", last_review={"reason": str(e)})
        log = self.repo / "automation/logs" / f"{task_id}-attempt{task['attempts']}.ndjson"
        out = self.runner.run(prompt, log)
        if out["returncode"] != 0 or not out.get("final"):
            status = "NEEDS_REVISION" if task["attempts"] < task["max_attempts"] else "FAIL"
            return self._status(task_id, status, last_log=str(log), last_review={"reason": "HEADLESS_FAILED", "timed_out": out.get("timed_out", False)})
        if self.dry_run:
            return self._status(task_id, "REVIEW_PENDING", last_log=str(log), last_review={"reason": "DRY_RUN"})
        try:
            self._assert_branch(branch)
            paths = changed_paths(self.repo)
            validate_paths(paths)
            if not paths:
                return self._status(task_id, "FAIL", last_log=str(log), last_review={"reason": "EMPTY_DIFF"})
            staged = stage_allowed(self.repo, paths)
            self._assert_branch(branch)
            if not staged.strip():
                return self._status(task_id, "FAIL", last_log=str(log), last_review={"reason": "EMPTY_STAGED_DIFF"})
            run(["git", "commit", "-m", f"automation: DSH task {task_id}"], self.repo)
            if commit_diff(self.repo) != staged:
                return self._status(task_id, "BLOCKED", last_log=str(log), last_review={"reason": "STAGED_COMMIT_DIFF_MISMATCH"})
            self._assert_branch(branch)
        except (ValueError, RuntimeError, subprocess.CalledProcessError) as e:
            return self._status(task_id, "BLOCKED", last_log=str(log), last_review={"reason": str(e)})
        run(["git", "push", "-u", "origin", branch], self.repo)
        task = self.store.load()["tasks"][task_id]
        if not task.get("pr_url"):
            pr = run(["gh", "pr", "create", "--draft", "--base", base_branch, "--head", branch, "--title", f"DSH: {task_id}", "--body", f"Automated DSH task: {task_id}"], self.repo, check=False)
            if pr.returncode != 0:
                return self._status(task_id, "FAIL", last_log=str(log), last_review={"reason": "PR_CREATE_FAILED", "stderr": pr.stderr[-2000:]})
            pr_url = pr.stdout.strip().splitlines()[-1] if pr.stdout.strip() else ""
        else:
            pr_url = task["pr_url"]
        # DSH never approves its own PR. The terminal automation state is
        # REVIEW_PENDING; a separate ChatGPT review acts on the GitHub PR.
        review = {"status": "REVIEW_PENDING", "reviewer": "chatgpt", "reason": "AWAITING_INDEPENDENT_PR_REVIEW"}
        return self._status(task_id, "REVIEW_PENDING", pr_url=pr_url, last_log=str(log), last_review=review)
