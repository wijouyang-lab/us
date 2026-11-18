# -*- coding: utf-8 -*-
"""pytest compatibility layer plus trusted workflow-context test fixture."""
import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Script-style tests execute at module import and end with sys.exit; run them
# through test_script_runner.py instead of pytest collection.
SCRIPT_TESTS = [
    "test_dashboard_data_stability.py",
    "test_dashboard_runtime.py",
    "test_event_key_p2.py",
    "test_milestone_win_rate.py",
    "test_options_reward_risk.py",
    "test_p05_repair_regression.py",
    "test_p3_5_rec_price_repair.py",
    "test_p3_data_quality.py",
    "test_portfolio_50000.py",
    "test_review_dashboard_fields.py",
]
collect_ignore = SCRIPT_TESTS


@pytest.fixture(autouse=True)
def _trusted_test_context(monkeypatch):
    # CLI tests exercise Publisher behavior, not GitHub's runner. Production
    # requires these values from the workflow; missing-context tests delete them.
    for key, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "wijouyang-lab/us",
        "GITHUB_WORKFLOW": "DSH Headless Task",
        "GITHUB_JOB": "publisher",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/deploy/dsh-automation-p0",
        "GITHUB_RUN_ID": "123456",
        "DSH_WORKFLOW_CONTEXT": "publisher",
    }.items():
        monkeypatch.setenv(key, value)
