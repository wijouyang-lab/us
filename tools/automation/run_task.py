"""CLI entry for one queued DSH task."""
from __future__ import annotations

import argparse
from pathlib import Path

from tools.automation.headless import HeadlessRunner
from tools.automation.orchestrator import Orchestrator
from tools.automation.state_store import TaskStore
from tools.automation.validate import validate_base, validate_branch, validate_task_id


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--branch", default="")
    ap.add_argument("--base-branch", default="main")
    ap.add_argument("--max-attempts", type=int, default=3, choices=[1, 2, 3])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--state", default="automation/state/tasks.json")
    args = ap.parse_args()
    try:
        task_id = validate_task_id(args.task_id)
        base = validate_base(args.base_branch)
        branch = validate_branch(args.branch or f"automation/{task_id}", base)
    except ValueError as e:
        print(f"INVALID_INPUT: {e}")
        return 2
    store = TaskStore(Path(args.state))
    store.enqueue(task_id, args.prompt, branch, max_attempts=args.max_attempts)
    task = Orchestrator(store, HeadlessRunner(), Path("."), dry_run=args.dry_run).run_with_repair(task_id, args.prompt, branch, base)
    print(f"TASK={task['task_id']} STATUS={task['status']} ATTEMPTS={task['attempts']}")
    return 0 if task["status"] in {"PASS", "REVIEW_PENDING", "NEEDS_REVISION"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
