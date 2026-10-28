# -*- coding: utf-8 -*-
"""Static contract tests for the research-only event capture workflow."""

from pathlib import Path

WORKFLOW = Path(".github/workflows/research-event-capture.yml")


def test_workflow_is_manual_only_and_separate():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "workflow_run:" not in text
    assert "push:" not in text
    assert "pull_request:" not in text
    assert "research-event-capture" in text


def test_workflow_skips_without_secret_and_uploads_artifacts():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "OFFICIAL_FEED_USER_AGENT" in text
    assert "not configured" in text
    assert "upload-artifact" in text
    assert "docs/research/event_forward_runs/" in text
    assert "retention-days: 90" in text


def test_workflow_does_not_hardcode_secret_values():
    text = WORKFLOW.read_text(encoding="utf-8")
    for forbidden in ("SECRET_VALUE", "api_key=", "apikey=", "password="):
        assert forbidden not in text
