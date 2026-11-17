"""Publisher job: validate artifact, apply files safely, push, create/reuse Draft PR."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

from tools.automation.artifact import _check_parents, read_manifest
from tools.automation.state_store import TaskStore


def cmd(args, cwd, check=True):
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=check)


def push_state(store, task_id, root, branch):
    store.save(store.load())
    cmd(["git", "add", "automation/state/tasks.json"], root)
    if cmd(["git", "diff", "--cached", "--quiet"], root, check=False).returncode == 0:
        return True
    cmd(["git", "commit", "-m", "automation: persist task state [skip ci]"], root)
    r = subprocess.run(["git", "-c", "credential.helper=!gh auth git-credential", "push", "origin", branch], cwd=root, text=True, capture_output=True)
    return r.returncode == 0


def apply_file(root: Path, src: Path, rel: str):
    target = _check_parents(root, rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Re-check after mkdir; then atomic replace in the same directory.
    target = _check_parents(root, rel)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".dsh-publish-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(src.read_bytes())
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", default="agent-artifact")
    ap.add_argument("--state", default="automation/state/tasks.json")
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()
    root = Path(args.repo).resolve()
    try:
        m = read_manifest(Path(args.artifact))
    except Exception as e:
        print(f"BLOCKED:{e}")
        return 1
    store = TaskStore(root / args.state)
    existing = store.load().get("tasks", {}).get(m["task_id"])
    if existing and existing.get("status") in {"REVIEW_PENDING", "PASS"}:
        print(f"SKIP_TERMINAL:{existing['status']}")
        return 0
    store.enqueue(m["task_id"], "", m["branch"])
    current = cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], root).stdout.strip()
    source = cmd(["git", "rev-parse", "HEAD"], root).stdout.strip()
    if current in {"main", "master"} or current != m["branch"]:
        store.update(m["task_id"], status="BLOCKED", last_review={"reason": f"BRANCH_GUARD:{current}"})
        return 1
    if source != m["source_commit_sha"]:
        store.update(m["task_id"], status="BLOCKED", last_review={"reason": "SOURCE_COMMIT_MISMATCH", "expected": m["source_commit_sha"], "actual": source})
        push_state(store, m["task_id"], root, m["branch"])
        print("BLOCKED:SOURCE_COMMIT_MISMATCH")
        return 1
    # Validate all target paths and hashes BEFORE any change.
    try:
        for f in m["files"]:
            _check_parents(root, f["path"])
        for rel in m["deletes"]:
            _check_parents(root, rel)
    except Exception as e:
        store.update(m["task_id"], status="BLOCKED", last_review={"reason": str(e)})
        return 1
    store.update(m["task_id"], status="PUBLISHING", last_review={"reason": "PUBLISHING"})
    try:
        for f in m["files"]:
            apply_file(root, Path(args.artifact) / "workspace" / f["path"], f["path"])
        for rel in m["deletes"]:
            target = _check_parents(root, rel)
            if target.exists():
                target.unlink()
        paths = [f["path"] for f in m["files"]] + list(m["deletes"])
        cmd(["git", "add", "-A", "--"] + paths, root)
        staged = cmd(["git", "diff", "--cached", "--binary"], root).stdout
        if not staged.strip():
            raise ValueError("EMPTY_STAGED_DIFF")
        cmd(["git", "commit", "-m", f"automation: DSH task {m['task_id']}"], root)
        cmd(["git", "-c", "credential.helper=!gh auth git-credential", "push", "-u", "origin", m["branch"]], root)
    except Exception as e:
        store.update(m["task_id"], status="FAIL", last_review={"reason": f"PUBLISH_FAILED:{e}"})
        push_state(store, m["task_id"], root, m["branch"])
        print(f"FAIL:{e}")
        return 1
    try:
        prs = cmd(["gh", "pr", "list", "--head", m["branch"], "--base", m["base_branch"], "--state", "open", "--json", "url,isDraft"], root).stdout
        pr_list = json.loads(prs or "[]")
        if pr_list:
            pr_url = pr_list[0]["url"]
        else:
            pr = subprocess.run(["gh", "pr", "create", "--draft", "--base", m["base_branch"], "--head", m["branch"], "--title", f"DSH: {m['task_id']}", "--body", f"Automated DSH task {m['task_id']}; independent review pending."], cwd=root, text=True, capture_output=True)
            if pr.returncode != 0:
                raise RuntimeError(f"PR_CREATE_FAILED:{pr.stderr[-1000:]}")
            pr_url = pr.stdout.strip().splitlines()[-1]
        store.update(m["task_id"], status="REVIEW_PENDING", pr_url=pr_url, last_review={"reviewer": "chatgpt", "reason": "AWAITING_INDEPENDENT_PR_REVIEW"})
        if not push_state(store, m["task_id"], root, m["branch"]):
            store.update(m["task_id"], last_review={"reviewer": "chatgpt", "reason": "STATE_PERSIST_FAILED"})
            print("STATE_PERSIST_FAILED")
            return 1
        print(f"STATUS=REVIEW_PENDING PR={pr_url}")
        return 0
    except Exception as e:
        store.update(m["task_id"], status="FAIL", last_review={"reason": f"PR_FAILED:{e}"})
        push_state(store, m["task_id"], root, m["branch"])
        print(f"FAIL:{e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
