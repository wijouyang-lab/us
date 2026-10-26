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
