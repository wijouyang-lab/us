import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from tools.invest_terminal.build_snapshot import build
from tools.invest_terminal.risk import build_risk
from tools.invest_terminal.strategy_registry import STRATEGIES, BENCHMARKS
from tools.paper_trading.engine import PaperEngine

ROOT = Path(__file__).resolve().parents[1]


def test_six_strategies_and_separate_benchmarks():
    assert [s["id"] for s in STRATEGIES] == ["value", "quality", "garp", "trend", "dividend", "hedge"]
    assert {s["status"] for s in STRATEGIES} <= {"PASS", "FAIL", "DATA_BLOCKED", "NOT_IMPLEMENTED"}
    assert {b["id"] for b in BENCHMARKS} == {"SPY", "QQQ", "BIL", "EQUAL_WEIGHT"}
    assert not any(b["id"] in {s["id"] for s in STRATEGIES} for b in BENCHMARKS)


def test_no_strategy_is_claimed_pass_without_validation():
    assert all(s["status"] != "PASS" for s in STRATEGIES)
    assert all(s["not_claimed"] for s in STRATEGIES)


def test_snapshot_uses_paper_account_and_does_not_fabricate_history(tmp_path):
    out = tmp_path / "terminal.json"
    PaperEngine(tmp_path / "paper")
    s = build(Path("dashboard/data/dashboard_data.json"), tmp_path / "paper", out)
    assert s["account"]["account_id"] == "PAPER-50000"
    assert s["account"]["initial_cash"] == 50000.0
    assert s["account"]["cash"] == 50000.0
    assert s["portfolio"]["performance"]["nav_series"] == []
    assert s["portfolio"]["performance"]["status"] in ("NO_HISTORY", "AVAILABLE")
    assert s["mode"] == "RESEARCH_AND_PAPER_ONLY"
    assert s["source"]["real_trading"] is False


def test_risk_empty_account_is_cash_only():
    r = build_risk({"cash": 50000, "positions": []}, {}, [])
    assert r["status"] == "CASH_ONLY"
    assert r["max_position_weight"] is None
    assert "NO_POSITIONS" in r["warnings"]


def test_risk_missing_price_is_not_zero():
    r = build_risk({"cash": 1000, "positions": [{"ticker": "AAPL", "shares": 2, "avg_cost": 100}]}, {}, [])
    assert r["missing_prices"] == ["AAPL"]
    assert r["positions"] == []


def test_paper_engine_rejects_stale_and_future_quotes(tmp_path):
    e = PaperEngine(tmp_path)
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="stale"):
        e.propose(client_order_id="old", ticker="AAPL", side="BUY", shares=1,
                  reference_price=100, price_asof=(now - timedelta(days=2)).isoformat(), strategy="VALUE")
    with pytest.raises(ValueError, match="future"):
        e.propose(client_order_id="future", ticker="AAPL", side="BUY", shares=1,
                  reference_price=100, price_asof=(now + timedelta(hours=1)).isoformat(), strategy="VALUE")


def test_order_requires_confirmation_and_cannot_auto_fill(tmp_path):
    e = PaperEngine(tmp_path)
    p = e.propose(client_order_id="x", ticker="AAPL", side="BUY", shares=1,
                  reference_price=100, price_asof=datetime.now(timezone.utc).isoformat(), strategy="VALUE")
    assert p["status"] == "PENDING"
    assert e.account()["positions"] == []
    e.confirm(p["order_id"], p["confirm_token"])
    assert len(e.account()["positions"]) == 1


def test_static_terminal_has_all_six_sections_and_mobile_viewport():
    html = (ROOT / "_local_terminal/terminal.html").read_text(encoding="utf-8")
    for panel in ("dashboard", "scanner", "strategies", "portfolio", "risk", "performance"):
        assert f'id="{panel}"' in html
    assert "width=device-width" in html
    js = (ROOT / "_local_terminal/terminal.js").read_text(encoding="utf-8")
    assert "invest_terminal_data.json" in js
    assert ("confirm_token" in js or "confirmation_token" in js)


def test_snapshot_json_is_committed_and_readable():
    s = json.loads((ROOT / "dashboard/data/invest_terminal_data.json").read_text(encoding="utf-8"))
    assert s["source"]["account_id"] == "PAPER-50000"
    assert len(s["strategies"]) == 6
    assert len(s["benchmarks"]) == 4
    assert s["scanner"]["count"] >= 1


def test_production_files_not_imported_by_new_package():
    for path in (ROOT / "tools/invest_terminal").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "import scan" not in text
        assert "import review" not in text
        assert "import evolve" not in text
        assert "ib_insync" not in text


def test_signal_adapters_fail_closed_without_fabricated_zero():
    from tools.invest_terminal.signals import evaluate
    out = evaluate({"ticker": "TEST", "pe_ttm": None, "pb": None, "roe": None})
    assert out["value"]["score"] is None
    assert out["quality"]["score"] is None
    assert out["garp"]["status"] == "DATA_BLOCKED"
    assert out["dividend"]["status"] == "DATA_BLOCKED"
    assert out["hedge"]["status"] == "DATA_BLOCKED"


def test_signal_value_research_only_when_metrics_exist():
    from tools.invest_terminal.signals import value
    r = value({"pe_ttm": 10.0, "pb": 2.0})
    assert r["status"] == "RESEARCH_ONLY"
    assert r["score"] is not None


def test_public_snapshot_never_contains_pending_confirmation_token(tmp_path):
    import json
    from datetime import datetime, timezone
    p = tmp_path / "paper"; e = PaperEngine(p)
    pending = e.propose(client_order_id="SECRET-1", ticker="AAPL", side="BUY", shares=1,
                        reference_price=100, price_asof=datetime.now(timezone.utc).isoformat(),
                        strategy="VALUE")
    assert pending["confirm_token"]
    out = tmp_path / "terminal.json"
    s = build(Path("dashboard/data/dashboard_data.json"), p, out)
    text = out.read_text(encoding="utf-8").lower()
    assert "confirm_token" not in text
    assert "confirmation_token" not in text
    assert pending["confirm_token"].lower() not in text
    assert s["account"]["pending_order_count"] == 1
    assert "confirm_token" not in json.dumps(s).lower()


def test_snapshot_without_persistent_db_is_explicitly_unavailable(tmp_path):
    out = tmp_path / "terminal.json"
    s = build(Path("dashboard/data/dashboard_data.json"), tmp_path / "missing-paper", out)
    assert s["account"]["account_status"] == "LOCAL_PAPER_DB_NOT_PRESENT"
    assert s["portfolio"]["nav"] is None
    assert s["source"]["paper_db_exists"] is False
    assert not (tmp_path / "missing-paper" / "paper.sqlite").exists()


def test_no_url_controlled_api_or_wildcard_cors():
    js = Path("_local_terminal/terminal.js").read_text(encoding="utf-8")
    html = Path("_local_terminal/terminal.html").read_text(encoding="utf-8")
    server = Path("tools/invest_terminal/server.py").read_text(encoding="utf-8")
    assert "URLSearchParams(location.search)" not in js
    assert "?api=" not in html
    assert "Access-Control-Allow-Origin" not in server
    assert 'ThreadingHTTPServer(("0.0.0.0"' not in server


def test_stock_research_selection_is_labelled_research_only():
    html = Path("_local_terminal/terminal.html").read_text(encoding="utf-8")
    js = Path("_local_terminal/terminal.js").read_text(encoding="utf-8")
    assert "Fundamental Selection V1" in html
    assert "RESEARCH_ONLY" in html
    assert "renderSelection" in js
    assert 'value_composite_experimental' not in js


def test_snapshot_carries_selection_counts():
    import json
    s = json.loads(Path("dashboard/data/invest_terminal_data.json").read_text(encoding="utf-8"))
    assert s["selection"]["status"] == "CURRENT_CROSS_SECTIONAL_RESEARCH"
    assert s["selection"]["value"]["candidate_issuers"] == 2529
    assert len(s["selection"]["value"]["top50"]) == 50
    assert s["selection"]["pit_status"] == "PIT_BACKTEST_BLOCKED"
