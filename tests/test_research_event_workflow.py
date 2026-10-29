# -*- coding: utf-8 -*-
"""Static contract tests for the research-only event capture workflow."""

from pathlib import Path

WORKFLOW = Path(".github/workflows/research-event-capture.yml")


def test_workflow_is_manual_and_weekday_scheduled_only():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "schedule:" in text
    assert 'cron: "15 21 * * 1-5"' in text
    assert "workflow_run:" not in text
    assert "push:" not in text
    assert "pull_request:" not in text
    assert "research-event-capture" in text


def test_workflow_uses_optional_secret_and_uploads_artifacts():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "OFFICIAL_FEED_USER_AGENT" in text
    assert "optional override" in text.lower()
    assert "upload-artifact" in text
    assert "docs/research/event_forward_runs/" in text
    assert "retention-days: 90" in text


def test_workflow_persists_archive_on_separate_branch():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "contents: write" in text
    assert "research/event-archive" in text
    assert "concurrency:" in text
    assert "event_archive_store import" in text
    assert "event_archive_store verify" in text
    assert "PYTHONPATH" in text
    assert 'git push origin "HEAD:${archive_branch}"' in text


def test_workflow_does_not_hardcode_secret_values():
    text = WORKFLOW.read_text(encoding="utf-8")
    for forbidden in ("SECRET_VALUE", "api_key=", "apikey=", "password="):
        assert forbidden not in text

def test_workflow_minimum_permissions_and_retention():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "permissions:\n  contents: read" in text
    assert "timeout-minutes: 15" in text
    assert "cancel-in-progress: false" in text
    assert "retention-days: 90" in text
    assert "if: always()" in text
    assert "write-all" not in text


def test_schedule_review_doc_exists():
    doc = Path("docs/research/EVENT_CAPTURE_SCHEDULE_REVIEW_2026-10-29.md")
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "not enabled" in text.lower()
    assert "21:15 UTC" in text
def test_scheduled_run_has_nonempty_default_feeds():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'feeds="${FEEDS:-bls_cpi,bls_employment,fed_all,fed_speeches}"' in text
    assert '--feeds "$feeds"' in text
def test_audit_decision_has_post_capture_buffer():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "+20 minutes" in text
    assert "+10 minutes" not in text
