from pathlib import Path


def test_capture_workflow_audits_readiness_at_the_captured_decision_time():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "research-event-factor-capture-once.yml"
    ).read_text(encoding="utf-8")
    assert "Audit point-in-time event archive readiness" in workflow
    assert "tools.research.audit_pit_event_data_readiness" in workflow
    assert '--decisions "$DECISIONS"' in workflow
    assert '--audited-at "$DECISION_AT"' in workflow
    assert 'event_archive_readiness_${GITHUB_RUN_ID}.json' in workflow
    assert "no labels are auto-approved" in workflow
