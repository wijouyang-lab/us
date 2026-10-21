# -*- coding: utf-8 -*-
"""Regression tests for one-shot research workflow push results."""

from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = (
    ".github/workflows/research-backfill-2y-once.yml",
    ".github/workflows/research-snapshots-2y-once.yml",
    ".github/workflows/research-snapshots-sp500-2y-once.yml",
    ".github/workflows/research-snapshots-sp500-pit-2y-once.yml",
)


def test_research_push_helper_success_does_not_fall_through_to_failure():
    for relative in WORKFLOWS:
        text = (REPO / relative).read_text(encoding="utf-8")
        assert re.search(r"(?m)^\s*if bash tools/ci/push_with_retry\.sh 3 5; then$", text), relative
        assert re.search(r'(?m)^\s*exit 0$', text), relative
        assert re.search(r'(?m)^\s*echo "::error::push failed after 3 retries"$', text), relative
        assert re.search(r"(?m)^\s*exit 1$", text), relative
        # The old bug called the helper unconditionally and then always exited 1,
        # so even a successful push made the workflow appear failed.
        assert not re.search(
            r'(?m)^\s*bash tools/ci/push_with_retry\.sh 3 5\s*\n\s*echo "❌ push failed after 3 retries"',
            text,
        ), relative


def test_research_workflows_remain_manual_and_do_not_run_production_scan_review_evolve():
    for relative in WORKFLOWS:
        text = (REPO / relative).read_text(encoding="utf-8")
        assert "workflow_dispatch:" in text
        assert "python scan.py" not in text
        assert "python review.py" not in text
        assert "python evolve.py" not in text
