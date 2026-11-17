"""Publisher: trusted-input validation, crash recovery, Draft PR, durable state."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

from tools.automation.artifact import _check_parents, artifact_digest, read_manifest
from tools.automation.state_store import TaskStore
from tools.automation.validate import validate_base, validate_branch, validate_task_id


def cmd(args, cwd, check=True):
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=check)


def push_state(store, root, branch):
    try:
        store.save(store.load())
        cmd(["git", "add", "automation/state/tasks.json"], root)
        if cmd(["git", "diff", "--cached", "--quiet"], root, check=False).returncode == 0:
            return True
        cmd(["git", "commit", "-m", "automation: persist task state [skip ci]"], root)
        r = subprocess.run(["git", "-c", "credential.helper=!gh auth git-credential", "push", "origin", branch], cwd=root, text=True, capture_output=True)
        return r.returncode == 0
    except Exception:
        return False


def mark(store, task_id, status, reason, root, branch, **extra):
    store.update(task_id, status=status, last_review={"reason": reason, **extra})
    ok = push_state(store, root, branch)
    if not ok:
        store.update(task_id, last_review={"reason": reason, **extra, "state_persist_failed": True})
        store.save(store.load())
        print("STATE_PERSIST_FAILED:REMOTE_NOT_SAVED")
    return ok


def apply_file(root: Path, src: Path, rel: str):
    target = _check_parents(root, rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    target = _check_parents(root, rel)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".dsh-publish-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(src.read_bytes())
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


STATE_COMMIT_SUBJECT = "automation: persist task state [skip ci]"


def _one_commit_state_only(root: Path, sha: str) -> bool:
    parents = cmd(["git", "rev-list", "--parents", "-n", "1", sha], root).stdout.split()
    if len(parents) != 2:
        return False
    subject = cmd(["git", "show", "-s", "--format=%s", sha], root).stdout.strip()
    if subject != STATE_COMMIT_SUBJECT:
        return False
    parent = parents[1]
    raw = cmd(["git", "diff-tree", "--no-commit-id", "--name-status", "-r", "-M", "-C", "--find-copies-harder", parent, sha], root).stdout.splitlines()
    if not raw:
        return False
    for line in raw:
        parts = line.split("\t")
        if len(parts) < 2 or parts[0][0] in {"R", "C"}:
            return False
        if not all(p.startswith("automation/state/") for p in parts[1:]):
            return False
    return True


def recovery_range_ok(root: Path, code: str, head: str) -> bool:
    """Only expected state commits may follow the artifact business commit."""
    if code == head:
        return True
    shas = cmd(["git", "rev-list", "--reverse", f"{code}..{head}"], root).stdout.splitlines()
    return all(_one_commit_state_only(root, sha) for sha in shas)


def state_only_ok(root: Path, source: str, head: str) -> bool:
    if source == head:
        return True
    shas = cmd(["git", "rev-list", "--reverse", f"{source}..{head}"], root).stdout.splitlines()
    return all(_one_commit_state_only(root, sha) for sha in shas)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", default="agent-artifact")
    ap.add_argument("--state", default="automation/state/tasks.json")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--branch", required=True)
    ap.add_argument("--base-branch", required=True)
    args = ap.parse_args()
    root = Path(args.repo).resolve()
    try:
        task_id = validate_task_id(args.task_id)
        base_branch = validate_base(args.base_branch)
        branch = validate_branch(args.branch, base_branch)
        m = read_manifest(Path(args.artifact))
    except Exception as e:
        print(f"BLOCKED:{e}")
        return 1
    if (m["task_id"], m["branch"], m["base_branch"]) != (task_id, branch, base_branch):
        print("BLOCKED:MANIFEST_INPUT_MISMATCH")
        return 1
    if m["timed_out"] is not False or m["tests_returncode"] != 0:
        print("BLOCKED:AGENT_NOT_CLEAN")
        return 1
    digest = artifact_digest(Path(args.artifact))
    base_sha = cmd(["git", "rev-parse", f"origin/{base_branch}"], root).stdout.strip()
    if base_sha != m["base_commit_sha"]:
        print("BLOCKED:BASE_COMMIT_MISMATCH")
        return 1
    store = TaskStore(root / args.state)
    existing = store.load().get("tasks", {}).get(task_id)
    if existing and existing.get("status") in {"REVIEW_PENDING", "PASS"}:
        print(f"SKIP_TERMINAL:{existing['status']}")
        return 0
    current = cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], root).stdout.strip()
    head = cmd(["git", "rev-parse", "HEAD"], root).stdout.strip()
    if current in {"main", "master"} or current != branch:
        store.enqueue(task_id, "", branch)
        mark(store, task_id, "BLOCKED", f"BRANCH_GUARD:{current}", root, branch)
        return 1
    resume_code = False
    reason = ((existing or {}).get("last_review") or {}).get("reason", "") if existing else ""
    recoverable_reasons = {"BUSINESS_PUSH_FAILED", "PUBLISHING_STATE_PUSH_FAILED", "STATE_PERSIST_FAILED", "PR_QUERY_FAILED", "PR_CREATE_FAILED", "READY_PR_BLOCKED", "MULTIPLE_PR_BLOCKED"}
    recoverable = bool(existing) and (existing.get("status") == "PUBLISHING" or (existing.get("status") == "BLOCKED" and reason in recoverable_reasons))
    if recoverable:
        if existing.get("agent_source_sha") != m["source_commit_sha"] or existing.get("artifact_digest") != digest:
            mark(store, task_id, "BLOCKED", "ARTIFACT_OR_SOURCE_MISMATCH", root, branch)
            return 1
        if cmd(["git", "merge-base", "--is-ancestor", existing["agent_source_sha"], head], root, check=False).returncode != 0:
            mark(store, task_id, "BLOCKED", "PUBLISHING_SOURCE_NOT_ANCESTOR", root, branch)
            return 1
        code = cmd(["git", "log", "-1", "--format=%H", f"--grep=artifact {digest}", head], root).stdout.strip()
        if code:
            if not recovery_range_ok(root, code, head):
                mark(store, task_id, "BLOCKED", "UNKNOWN_COMMIT_AFTER_ARTIFACT", root, branch)
                return 1
            resume_code = True
        else:
            if not state_only_ok(root, existing["agent_source_sha"], head):
                mark(store, task_id, "BLOCKED", "PUBLISHING_UNRECOGNIZED_COMMIT", root, branch)
                return 1
    else:
        if head != m["source_commit_sha"]:
            store.enqueue(task_id, "", branch)
            mark(store, task_id, "BLOCKED", "SOURCE_COMMIT_MISMATCH", root, branch)
            return 1
        store.enqueue(task_id, "", branch)
        task = store.load()["tasks"][task_id]
        store.update(task_id, status="PUBLISHING", attempts=task["attempts"] + 1, agent_source_sha=m["source_commit_sha"], base_commit_sha=m["base_commit_sha"], artifact_digest=digest, branch=branch, base_branch=base_branch)
        if not push_state(store, root, branch):
            mark(store, task_id, "PUBLISHING", "PUBLISHING_STATE_PUSH_FAILED", root, branch)
            return 1
    try:
        if not resume_code:
            for f in m["files"]:
                _check_parents(root, f["path"])
            for rel in m["deletes"]:
                _check_parents(root, rel)
            for f in m["files"]:
                apply_file(root, Path(args.artifact) / "workspace" / f["path"], f["path"])
            for rel in m["deletes"]:
                target = _check_parents(root, rel)
                if target.exists():
                    target.unlink()
            paths = [f["path"] for f in m["files"]] + list(m["deletes"])
            cmd(["git", "add", "-A", "--"] + paths, root)
            if cmd(["git", "diff", "--cached", "--quiet"], root, check=False).returncode == 0:
                # No business change is safe only when the code commit already exists.
                existing_code = cmd(["git", "log", "-1", "--format=%H", f"--grep=artifact {digest}", head], root).stdout.strip()
                if not existing_code:
                    mark(store, task_id, "FAIL", "EMPTY_STAGED_DIFF", root, branch)
                    return 1
            else:
                cmd(["git", "commit", "-m", f"automation: DSH task {task_id} artifact {digest}"], root)
        published = cmd(["git", "rev-parse", "HEAD"], root).stdout.strip()
        store.update(task_id, published_sha=published)
    except Exception as e:
        mark(store, task_id, "FAIL", f"PUBLISH_FAILED:{e}", root, branch)
        print(f"FAIL:{e}")
        return 1
    try:
        cmd(["git", "-c", "credential.helper=!gh auth git-credential", "push", "-u", "origin", branch], root)
    except Exception as e:
        store.update(task_id, published_sha=published)
        mark(store, task_id, "PUBLISHING", "BUSINESS_PUSH_FAILED", root, branch)
        print(f"RECOVERABLE:BUSINESS_PUSH_FAILED:{e}")
        return 1
    try:
        try:
            prs_raw = cmd(["gh", "pr", "list", "--head", branch, "--base", base_branch, "--state", "open", "--json", "url,isDraft,headRefName,baseRefName"], root).stdout
        except Exception as e:
            raise RuntimeError(f"PR_QUERY_FAILED:{e}")
        prs = json.loads(prs_raw or "[]")
        if len(prs) > 1:
            raise RuntimeError("MULTIPLE_OPEN_PRS")
        if prs:
            pr = prs[0]
            if not pr.get("isDraft"):
                raise RuntimeError("NON_DRAFT_PR_EXISTS")
            if pr.get("headRefName") != branch or pr.get("baseRefName") != base_branch:
                raise RuntimeError("PR_REF_MISMATCH")
            pr_url = pr["url"]
        else:
            proc = subprocess.run(["gh", "pr", "create", "--draft", "--base", base_branch, "--head", branch, "--title", f"DSH: {task_id}", "--body", f"Automated DSH task {task_id}; independent review pending."], cwd=root, text=True, capture_output=True)
            if proc.returncode != 0:
                raise RuntimeError(f"PR_CREATE_FAILED:{proc.stderr[-1000:]}")
            pr_url = proc.stdout.strip().splitlines()[-1]
            view = subprocess.run(["gh", "pr", "view", pr_url, "--json", "url,isDraft,headRefName,baseRefName"], cwd=root, text=True, capture_output=True)
            if view.returncode != 0:
                raise RuntimeError("PR_QUERY_FAILED")
            v = json.loads(view.stdout)
            if not v.get("isDraft") or v.get("url") != pr_url or v.get("headRefName") != branch or v.get("baseRefName") != base_branch:
                raise RuntimeError("DRAFT_PR_VERIFY_FAILED")
        store.update(task_id, status="REVIEW_PENDING", pr_url=pr_url, last_review={"reviewer": "chatgpt", "reason": "AWAITING_INDEPENDENT_PR_REVIEW"})
        if not push_state(store, root, branch):
            store.update(task_id, last_review={"reason": "STATE_PERSIST_FAILED", "pr_url": pr_url})
            store.save(store.load())
            print("STATE_PERSIST_FAILED:PR_EXISTS")
            return 1
        print(f"STATUS=REVIEW_PENDING PR={pr_url}")
        return 0
    except Exception as e:
        text = str(e)
        if "PR_CREATE_FAILED" in text or "DRAFT_PR_VERIFY_FAILED" in text:
            mark(store, task_id, "PUBLISHING", "PR_CREATE_FAILED", root, branch)
            print(f"RECOVERABLE:PR_CREATE_FAILED:{e}")
        elif "MULTIPLE_OPEN_PRS" in text:
            mark(store, task_id, "BLOCKED", "MULTIPLE_PR_BLOCKED", root, branch)
            print(f"BLOCKED:MULTIPLE_PR_BLOCKED:{e}")
        elif "NON_DRAFT" in text or "PR_REF_MISMATCH" in text:
            mark(store, task_id, "BLOCKED", "READY_PR_BLOCKED", root, branch)
            print(f"BLOCKED:READY_PR_BLOCKED:{e}")
        elif "PR_QUERY_FAILED" in text or "pr list" in text.lower():
            mark(store, task_id, "PUBLISHING", "PR_QUERY_FAILED", root, branch)
            print(f"RECOVERABLE:PR_QUERY_FAILED:{e}")
        else:
            mark(store, task_id, "FAIL", "PERMANENT_PUBLISH_FAILURE", root, branch)
            print(f"FAIL:PERMANENT_PUBLISH_FAILURE:{e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
