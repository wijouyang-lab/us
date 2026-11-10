from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_p7_shadow_has_no_write_or_push_and_no_user_branch():
    text = (ROOT / ".github/workflows/p7-shadow-daily.yml").read_text(encoding="utf-8")
    assert "contents: write" not in text
    assert "git push" not in text
    assert "inputs.branch" not in text
    assert "github.event.inputs.branch" not in text
    assert "contents: read" in text
    assert "actions/upload-artifact" in text


def test_dashboard_workflow_has_no_terminal_publication():
    text = (ROOT / ".github/workflows/dashboard-data.yml").read_text(encoding="utf-8")
    assert "invest_terminal_data.json" not in text
    assert "tools.invest_terminal.build_snapshot" not in text
    assert "investTerminalLink" not in (ROOT / "index.html").read_text(encoding="utf-8")


def test_terminal_snapshot_is_ignored():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "dashboard/data/invest_terminal_data.json" in text
