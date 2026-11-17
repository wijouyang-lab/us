"""Preflight: validate inputs and fail closed when main protection is absent."""
from __future__ import annotations

import argparse
import subprocess
import sys

from tools.automation.validate import validate_base, validate_branch, validate_task_id


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--branch", required=True)
    ap.add_argument("--base-branch", default="main")
    args = ap.parse_args()
    try:
        validate_task_id(args.task_id)
        validate_base(args.base_branch)
        validate_branch(args.branch, args.base_branch)
    except ValueError as e:
        print(f"BLOCKED:{e}")
        return 1
    slug = subprocess.run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"], text=True, capture_output=True)
    if slug.returncode != 0 or not slug.stdout.strip():
        print("BLOCKED:REPO_IDENTITY_UNAVAILABLE")
        return 1
    r = subprocess.run(["gh", "api", f"repos/{slug.stdout.strip()}/branches/main", "--jq", ".protected"], text=True, capture_output=True)
    if r.returncode != 0 or r.stdout.strip().lower() != "true":
        print("BLOCKED:MAIN_PROTECTION_UNVERIFIED")
        return 1
    print("PREFLIGHT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
