import json
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


def test_p7_artifact_has_no_private_snapshot():
    text = (ROOT / ".github/workflows/p7-shadow-daily.yml").read_text(encoding="utf-8")
    assert "tools.invest_terminal.build_snapshot" not in text
    assert "invest_terminal_data.json" not in text
    assert "paper.sqlite" not in text


def test_terminal_artifact_is_assets_only():
    text = (ROOT / ".github/workflows/research-invest-terminal.yml").read_text(encoding="utf-8")
    assert "invest_terminal_data.json" not in text
    assert "paper.sqlite" not in text
    assert "path: _local_terminal/" in text


def test_pages_build_workflow_is_build_only():
    text = (ROOT / ".github/workflows/pages-build-audit.yml").read_text(encoding="utf-8")
    assert "actions/jekyll-build-pages@v1" in text
    assert "actions/deploy-pages" not in text
    assert "pages: write" not in text
    assert "id-token: write" not in text
    for check in ("_site/terminal.html", "_site/terminal", "_site/_local_terminal", "_site/dashboard/data/invest_terminal_data.json"):
        assert check in text


def test_snapshot_redaction_without_local_db(tmp_path):
    from tools.invest_terminal.build_snapshot import build
    s = build(ROOT / "dashboard/data/dashboard_data.json", tmp_path / "missing-paper", tmp_path / "snap.json")
    assert s["source"]["paper_db_exists"] is False
    assert s["account"]["account_status"] == "LOCAL_PAPER_DB_NOT_PRESENT"
    raw = json.dumps(s)
    for forbidden in ("confirm_token", "csrf", "session_secret", "paper.sqlite-wal", "paper.sqlite-shm"):
        assert forbidden not in raw
    assert "C:\\" not in raw and "C:/" not in raw

