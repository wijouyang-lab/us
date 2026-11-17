"""Publisher job: validate artifact, apply files, push, create Draft PR, persist state."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from tools.automation.artifact import read_manifest
from tools.automation.state_store import TaskStore, now


def cmd(args, check=True):
    return subprocess.run(args, text=True, capture_output=True, check=check)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", default="agent-artifact")
    ap.add_argument("--state", default="automation/state/tasks.json")
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()
    root = Path(args.repo)
    try:
        m = read_manifest(Path(args.artifact))
    except Exception as e:
        print(f"BLOCKED:{e}")
        return 1
    store = TaskStore(root / args.state)
    store.enqueue(m["task_id"], "", m["branch"])
    store.update(m["task_id"], status="RUNNING")
    try:
        cur = cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root).stdout.strip()
        if cur in {"main", "master"} or cur != m["branch"]:
            raise RuntimeError(f"BRANCH_GUARD:{cur}")
        workspace = Path(args.artifact) / "workspace"
        files = m.get("files", [])
        deletes = m.get("deletes", [])
        for f in files:
            rel = f["path"]
            src = workspace / rel
            dst = root / rel
            if not src.is_file() or src.is_symlink():
                raise ValueError(f"INVALID_ARTIFACT_FILE:{rel}")
            if hashlib.sha256(src.read_bytes()).hexdigest() != f["sha256"]:
                raise ValueError(f"HASH_MISMATCH:{rel}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
            if dst.is_symlink():
                raise ValueError(f"SYMLINK_TARGET:{rel}")
        for rel in deletes:
            p = root / rel
            if p.exists():
                p.unlink()
        paths = [f["path"] for f in files] + list(deletes)
        cmd(["git", "add", "-A", "--"] + paths, cwd=root)
        staged = cmd(["git", "diff", "--cached", "--binary"], cwd=root).stdout
        if not staged.strip():
            raise ValueError("EMPTY_STAGED_DIFF")
        cmd(["git", "commit", "-m", f"automation: DSH task {m['task_id']}"], cwd=root)
        cmd(["git", "-c", "credential.helper=!gh auth git-credential", "push", "-u", "origin", m["branch"]], cwd=root)
        pr = subprocess.run(["gh", "pr", "create", "--draft", "--base", m["base_branch"], "--head", m["branch"], "--title", f"DSH: {m['task_id']}", "--body", f"Automated DSH task {m['task_id']}; independent review pending."], cwd=root, text=True, capture_output=True)
        if pr.returncode != 0:
            store.update(m["task_id"], status="FAIL", last_review={"reason": "PR_CREATE_FAILED", "stderr": pr.stderr[-2000:]})
            return 1
        pr_url = pr.stdout.strip().splitlines()[-1] if pr.stdout.strip() else ""
        store.update(m["task_id"], status="REVIEW_PENDING", pr_url=pr_url, last_review={"reviewer": "chatgpt", "reason": "AWAITING_INDEPENDENT_PR_REVIEW"}, last_log="")
        cmd(["git", "add", str(Path(args.state))], cwd=root)
        cmd(["git", "commit", "-m", "automation: persist task state [skip ci]"], cwd=root)
        cmd(["git", "-c", "credential.helper=!gh auth git-credential", "push", "origin", m["branch"]], cwd=root)
        print(f"STATUS=REVIEW_PENDING PR={pr_url}")
        return 0
    except Exception as e:
        store.update(m["task_id"], status="BLOCKED", last_review={"reason": str(e)})
        print(f"BLOCKED:{e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
