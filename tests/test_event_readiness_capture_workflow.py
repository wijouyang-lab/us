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


def test_capture_workflow_uses_single_shell_continuations_and_valid_csv_newlines():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "research-event-factor-capture-once.yml"
    ).read_text(encoding="utf-8")
    command_fragments = (
        "python -m tools.research.audit_pit_event_data_readiness ",
        '--archive "$ARCHIVE" ',
        '--decisions "$DECISIONS" ',
        '--audited-at "$DECISION_AT" ',
    )
    for fragment in command_fragments:
        line = next((line for line in workflow.splitlines() if fragment in line), None)
        assert line is not None, f"missing readiness command fragment: {fragment}"
        assert line.endswith("\\"), f"missing shell continuation: {line}"
        assert not line.endswith("\\\\"), f"doubled shell continuation: {line}"
    csv_line = next(line.strip() for line in workflow.splitlines() if "printf 'decision_at" in line)
    assert csv_line == "printf 'decision_at\\n%s\\n' \"$DECISION_AT\" > \"$DECISIONS\""


def test_capture_workflow_collects_prices_and_runs_descriptive_event_study():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "research-event-factor-capture-once.yml"
    ).read_text(encoding="utf-8")
    assert "Capture recent prices and run descriptive event-response study" in workflow
    assert "tools.research.capture_event_response_prices" in workflow
    assert "tools.research.pit_event_response_study" in workflow
    assert '--study-end-date "$STUDY_END_DATE"' in workflow
    assert "--price-basis auto" in workflow
    assert "no price rows" in workflow
