"""Adapter boundaries and an injectable Publisher core.

The production CLI is intentionally blocked until a real distributed lock is
implemented. This core exists so publishing decisions can be tested with fakes
and without any real Git/GitHub/state access.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Pr:
    url: str
    draft: bool
    head: str
    base: str


class GitPort(Protocol):
    def head(self) -> str: ...
    def branch(self) -> str: ...
    def base_sha(self, base: str) -> str: ...


class GitHubPort(Protocol):
    def list_prs(self, head: str, base: str) -> list[Pr]: ...
    def create_draft(self, head: str, base: str, task_id: str) -> str: ...
    def get_pr(self, url: str) -> Pr: ...


class StatePort(Protocol):
    def task(self, task_id: str) -> dict | None: ...
    def persist(self, task_id: str, **fields) -> bool: ...


def _valid_pr_url(value: str) -> bool:
    """Accept only canonical PR URLs from this repository."""
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname == "github.com"
        and port in (None, 443)
        and parsed.username is None
        and parsed.password is None
        and re.fullmatch(r"/wijouyang-lab/us/pull/[1-9][0-9]*", parsed.path) is not None
        and not parsed.query
        and not parsed.fragment
    )


def choose_pr(prs: list[Pr]) -> tuple[str, str] | tuple[None, str]:
    if len(prs) > 1:
        return None, "MULTIPLE_PR_BLOCKED"
    if not prs:
        return "create", ""
    pr = prs[0]
    if not pr.draft:
        return None, "READY_PR_BLOCKED"
    return "reuse", pr.url


def publish(manifest: dict, trusted: dict, git: GitPort, github: GitHubPort, state: StatePort) -> dict:
    """Perform the gated PR decision without touching files or remotes directly."""
    for key in ("task_id", "branch", "base_branch"):
        if manifest.get(key) != trusted.get(key):
            return {"ok": False, "reason": "MANIFEST_INPUT_MISMATCH"}
    existing = state.task(manifest["task_id"])
    if existing and existing.get("status") in {"REVIEW_PENDING", "PASS"}:
        pr_url = existing.get("pr_url")
        if not _valid_pr_url(pr_url):
            return {"ok": False, "reason": "PR_URL_INVALID"}
        return {"ok": True, "status": existing["status"], "pr_url": pr_url, "skipped": True}
    if git.branch() != manifest["branch"]:
        return {"ok": False, "reason": "BRANCH_GUARD"}
    if git.head() != manifest["source_commit_sha"]:
        return {"ok": False, "reason": "SOURCE_COMMIT_MISMATCH"}
    if git.base_sha(manifest["base_branch"]) != manifest["base_commit_sha"]:
        return {"ok": False, "reason": "BASE_COMMIT_MISMATCH"}
    try:
        prs = github.list_prs(manifest["branch"], manifest["base_branch"])
        choice, value = choose_pr(prs)
    except Exception:
        return {"ok": False, "reason": "PR_QUERY_FAILED"}
    if choice != "create" and choice != "reuse":
        return {"ok": False, "reason": value}
    if choice == "reuse":
        pr = prs[0]
        if not _valid_pr_url(pr.url):
            return {"ok": False, "reason": "PR_URL_INVALID"}
        if pr.head != manifest["branch"] or pr.base != manifest["base_branch"]:
            return {"ok": False, "reason": "PR_REF_MISMATCH"}
        value = pr.url
    else:
        try:
            url = github.create_draft(manifest["branch"], manifest["base_branch"], manifest["task_id"])
            if not _valid_pr_url(url):
                return {"ok": False, "reason": "PR_URL_INVALID"}
            pr = github.get_pr(url)
        except Exception:
            return {"ok": False, "reason": "PR_CREATE_FAILED"}
        if (
            not _valid_pr_url(pr.url)
            or pr.url != url
            or not pr.draft
            or pr.head != manifest["branch"]
            or pr.base != manifest["base_branch"]
        ):
            return {"ok": False, "reason": "DRAFT_PR_VERIFY_FAILED"}
        value = url
    if not state.persist(manifest["task_id"], status="REVIEW_PENDING", pr_url=value):
        return {"ok": False, "reason": "STATE_PERSIST_FAILED"}
    return {"ok": True, "status": "REVIEW_PENDING", "pr_url": value, "skipped": False}
