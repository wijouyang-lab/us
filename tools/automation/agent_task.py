"""Agent job: DSH only; no GitHub writes; emit a validated file artifact."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from tools.automation.artifact import build_artifact
from tools.automation.changes import changed_paths, validate_paths
from tools.automation.headless import HeadlessRunner
from tools.automation.redact import redact
from tools.automation.validate import validate_base, validate_branch, validate_task_id


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--branch", required=True)
    ap.add_argument("--base-branch", default="main")
    ap.add_argument("--out", default="agent-artifact")
    ap.add_argument("--log", default="automation/logs/agent.ndjson")
    args = ap.parse_args()
    try:
        task_id = validate_task_id(args.task_id)
        validate_base(args.base_branch)
        validate_branch(args.branch, args.base_branch)
    except ValueError as e:
        print(f"INVALID_INPUT:{e}")
        return 2
    out = Path(args.out)
    source = subprocess.run(["git", "rev-parse", "HEAD"], text=True, capture_output=True).stdout.strip()
    base = subprocess.run(["git", "rev-parse", f"origin/{args.base_branch}"], text=True, capture_output=True).stdout.strip()
    result = HeadlessRunner().run(args.prompt, Path(args.log))
    manifest = {"task_id": task_id, "branch": args.branch, "base_branch": args.base_branch, "source_commit_sha": source, "base_commit_sha": base, "status": "AGENT_FAILED", "timed_out": result.get("timed_out", False), "diagnostic_summary": redact(result.get("final") or "")}
    if result["returncode"] != 0 or not result.get("final"):
        build_artifact(Path("."), out, manifest, [])
        return 1
    try:
        paths = changed_paths(Path("."))
        validate_paths(paths)
        tests = subprocess.run(["python", "-m", "pytest", "-q"], text=True, capture_output=True, timeout=600)
        manifest["tests_returncode"] = tests.returncode
        manifest["diagnostic_summary"] = redact((tests.stdout + tests.stderr)[-4000:])
        if tests.returncode != 0:
            manifest["status"] = "AGENT_TESTS_FAILED"
            build_artifact(Path("."), out, manifest, paths)
            return 1
        manifest["status"] = "AGENT_COMPLETE"
        build_artifact(Path("."), out, manifest, paths)
        return 0
    except Exception as e:
        manifest["status"] = "AGENT_BLOCKED"
        manifest["error"] = str(e)
        build_artifact(Path("."), out, manifest, [])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
