import os

import pytest


@pytest.fixture(autouse=True)
def _trusted_test_context(monkeypatch):
    # Tests exercise CLI behavior, not GitHub's runner. Production requires these
    # to be supplied by the workflow; a missing-context test removes them.
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
