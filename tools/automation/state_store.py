"""Atomic JSON task state used by the DSH automation loop."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

STATUSES = {
    "QUEUED", "RUNNING", "REVIEW_PENDING", "NEEDS_REVISION",
    "PASS", "FAIL", "BLOCKED",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict:
        if not self.path.exists():
            return {"version": 1, "updated_at": now(), "tasks": {}}
        return json.loads(self.path.read_text(encoding="utf-8-sig"))

    def save(self, data: dict) -> None:
        data["updated_at"] = now()
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".tasks-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, sort_keys=True)
                fh.write("\n")
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def enqueue(self, task_id: str, prompt: str, branch: str, max_attempts: int = 3) -> dict:
        data = self.load()
        if task_id in data["tasks"]:
            return data["tasks"][task_id]
        data["tasks"][task_id] = {
            "task_id": task_id, "prompt": prompt, "branch": branch,
            "status": "QUEUED", "attempts": 0, "max_attempts": max_attempts,
            "pr_url": "", "last_review": None, "last_log": "",
            "created_at": now(), "updated_at": now(), "history": [],
        }
        self.save(data)
        return data["tasks"][task_id]

    def claim(self, task_id: str) -> dict:
        data = self.load()
        task = data["tasks"][task_id]
        if task["status"] not in {"QUEUED", "NEEDS_REVISION"}:
            raise ValueError(f"TASK_NOT_CLAIMABLE:{task['status']}")
        task["status"] = "RUNNING"
        task["attempts"] += 1
        task["updated_at"] = now()
        task["history"].append({"at": now(), "event": "claim", "attempt": task["attempts"]})
        self.save(data)
        return task

    def update(self, task_id: str, **fields) -> dict:
        data = self.load()
        task = data["tasks"][task_id]
        if "status" in fields and fields["status"] not in STATUSES:
            raise ValueError("INVALID_STATUS")
        task.update(fields)
        task["updated_at"] = now()
        self.save(data)
        return task

    def resume_protection_blocked(self, task_id: str) -> bool:
        data = self.load()
        task = data["tasks"].get(task_id)
        if not task or task.get("status") != "BLOCKED":
            return False
        reason = (task.get("last_review") or {}).get("reason")
        if reason != "MAIN_PROTECTION_UNVERIFIED":
            return False
        task["status"] = "QUEUED"
        task["updated_at"] = now()
        task["history"].append({"at": now(), "event": "resume_protection_blocked", "status": "QUEUED"})
        self.save(data)
        return True

    def recover_stale(self) -> list[str]:
        """Recover RUNNING tasks left by a crashed workflow."""
        data = self.load()
        recovered = []
        for task in data["tasks"].values():
            if task["status"] == "RUNNING":
                task["status"] = "QUEUED" if task["attempts"] < task["max_attempts"] else "FAIL"
                task["updated_at"] = now()
                task["history"].append({"at": now(), "event": "recover_stale", "status": task["status"]})
                recovered.append(task["task_id"])
        if recovered:
            self.save(data)
        return recovered
