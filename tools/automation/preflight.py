"""Preflight: main-only, fail-closed protection checks."""
from __future__ import annotations

import argparse
import json
import subprocess

from tools.automation.validate import validate_base, validate_branch, validate_task_id


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--branch", required=True)
    ap.add_argument("--base-branch", default="main")
    ap.add_argument("--dry-run", action="store_true")
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
    branch = subprocess.run(["gh", "api", f"repos/{slug.stdout.strip()}/branches/main"], text=True, capture_output=True)
    if branch.returncode != 0:
        print("BLOCKED:PROTECTION_RULES_UNVERIFIED")
        return 1
    try:
        if json.loads(branch.stdout).get("protected") is not True:
            print("BLOCKED:MAIN_PROTECTION_UNVERIFIED")
            return 1
    except Exception:
        print("BLOCKED:PROTECTION_RULES_UNVERIFIED")
        return 1
    rules = subprocess.run(["gh", "api", f"repos/{slug.stdout.strip()}/branches/main/protection"], text=True, capture_output=True)
    if rules.returncode != 0:
        print("BLOCKED:PROTECTION_RULES_UNVERIFIED")
        return 1
    try:
        p = json.loads(rules.stdout)
        ok = (
            bool(p.get("required_status_checks"))
            and bool(p.get("required_pull_request_reviews"))
            and p.get("allow_force_pushes", {}).get("enabled") is False
            and p.get("enforce_admins", {}).get("enabled") is True
        )
    except Exception:
        ok = False
    if not ok:
        print("BLOCKED:PROTECTION_RULES_UNVERIFIED")
        return 1
    if args.dry_run:
        print("DRY_RUN_VALIDATION_ONLY")
        return 0
    print("PREFLIGHT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
