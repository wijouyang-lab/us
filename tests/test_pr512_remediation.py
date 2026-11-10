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


def test_terminal_is_not_in_pages_root():
    # GitHub Pages is legacy main/root Jekyll. Underscore directories are
    # excluded by Jekyll; no root terminal file may exist.
    assert not (ROOT / "terminal.html").exists()
    assert not (ROOT / "terminal").exists()
    assert (ROOT / "_local_terminal/terminal.html").exists()
    assert not (ROOT / ".nojekyll").exists()
    text = (ROOT / ".github/workflows/research-invest-terminal.yml").read_text(encoding="utf-8")
    assert "_local_terminal" in text
    assert "test -f terminal.html" not in text
