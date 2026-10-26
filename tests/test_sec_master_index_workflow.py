from pathlib import Path


def test_sec_master_index_shell_continuations_are_single_backslashes():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "research-event-factor-capture-once.yml"
    ).read_text(encoding="utf-8")
    command_fragments = (
        "if ! python -m tools.research.sec_master_index_capture ",
        '--universe "$UNIVERSE" ',
        '--start-date "$INDEX_START_DATE" ',
        '--end-date "$INDEX_END_DATE" ',
    )
    for fragment in command_fragments:
        line = next((line for line in workflow.splitlines() if fragment in line), None)
        assert line is not None, f"missing SEC master-index command fragment: {fragment}"
        assert line.endswith("\\"), f"command line lacks a shell continuation: {line}"
        assert not line.endswith("\\\\"), f"command line has a doubled shell continuation: {line}"

def test_sec_master_index_failure_writes_structured_research_record():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "research-event-factor-capture-once.yml"
    ).read_text(encoding="utf-8")
    assert 'SEC_CAPTURE_ERROR="data/research/event-capture/sec_master_index_${GITHUB_RUN_ID}.error.json"' in workflow
    assert '"source": "sec_edgar_master_index"' in workflow
    assert '"status": "failed"' in workflow
    assert '"historical_pit_eligible": False' in workflow
    assert "A retrieval failure must not be interpreted as proof that no filings occurred." in workflow
    assert '2>&1; then' in workflow

