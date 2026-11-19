import json
from pathlib import Path

from tools.invest_terminal.build_snapshot import build
from tools.paper_trading.engine import PaperEngine

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_timestamp_and_no_db_status(tmp_path):
    dashboard = json.loads((ROOT / "dashboard/data/dashboard_data.json").read_text(encoding="utf-8"))
    dashboard["generated_at"] = "2026-11-06T00:00:00Z"
    p = tmp_path / "dashboard.json"; p.write_text(json.dumps(dashboard), encoding="utf-8")
    s = build(p, tmp_path / "no-paper", tmp_path / "snap.json")
    assert s["source"]["dashboard_generated_at"] == "2026-11-06T00:00:00Z"
    assert s["source"]["paper_db_exists"] is False
    assert s["account"]["account_status"] == "LOCAL_PAPER_DB_NOT_PRESENT"
    assert s["portfolio"]["nav"] is None


def test_local_db_is_labeled_export_not_live(tmp_path):
    dashboard = ROOT / "dashboard/data/dashboard_data.json"
    PaperEngine(tmp_path / "paper")
    s = build(dashboard, tmp_path / "paper", tmp_path / "snap.json")
    assert s["source"]["paper_db_exists"] is True
    assert s["account"]["account_status"] == "LOCAL_DB_EXPORT"
    assert s["account"]["cash"] == 50000.0


def test_dashboard_workflow_builds_snapshot_and_guards_loop():
    y = (ROOT / ".github/workflows/dashboard-data.yml").read_text(encoding="utf-8")
    assert "python -m tools.invest_terminal.build_snapshot" in y
    assert "dashboard/data/invest_terminal_data.json" in y
    assert "[skip ci]" in y
    assert "git add dashboard/data/dashboard_data.json dashboard/data/invest_terminal_data.json" in y


def test_terminal_workflow_paths_are_separate():
    y = (ROOT / ".github/workflows/research-invest-terminal.yml").read_text(encoding="utf-8")
    assert '- "tests/test_paper_trading_platform.py tests/test_invest_terminal_server.py"' not in y
    assert '- "tests/test_paper_trading_platform.py"' in y
    assert '- "tests/test_invest_terminal_server.py"' in y
    assert '- "dashboard/data/dashboard_data.json"' in y
