import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P8 = ROOT / "data/research/p8"


def test_inventory_is_actual_and_blocks_missing_indices():
    d = json.loads((P8 / "inventory.json").read_text(encoding="utf-8"))
    assert len(d["modules"]) == 18
    blocked = {r["module"] for r in d["modules"] if not r["done"]}
    assert "Nasdaq-100 membership" in blocked
    assert "Dow 30 membership" in blocked
    assert d["pit"]["sp500_effective_membership"] is True
    assert d["pit"]["nasdaq100"] is False
    assert d["pit"]["dow30"] is False


def test_pit_screen_coverage_and_all_no_go():
    d = json.loads((P8 / "pit_strategy_results.json").read_text(encoding="utf-8"))
    assert d["coverage_mean"] > 0.90
    assert d["coverage_mean"] < 0.95
    assert len(d["strategies"]) == 6
    assert all(v["gate"] == "NO-GO" for v in d["strategies"].values())
    assert d["multiple_testing"]["hypotheses"] == 6


def test_etf_results_are_not_alpha_claims():
    d = json.loads((P8 / "etf_multiasset_results.json").read_text(encoding="utf-8"))
    assert set(d["strategies"]) == {"TREND_RISK", "RISK_PARITY"}
    assert all(v["oos_cagr"] < d["benchmarks"]["SPY"]["oos_cagr"] for v in d["strategies"].values())
    assert d["status"] == "ETF_MULTIASSET_PRELIMINARY"


def test_gate_has_no_go_and_all_rows():
    d = json.loads((P8 / "p8_status.json").read_text(encoding="utf-8"))
    assert d["status"] == "P8_FIRST_ROUND_NO_GO"
    assert d["go_count"] == 0
    assert len(d["strategy_gate"]) == 8
    assert all(r["status"] == "NO-GO" for r in d["strategy_gate"])


def test_no_nasdaq_or_dow_substitution():
    with (P8 / "universe_membership.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for idx in ("NASDAQ100", "DOW30"):
        x = [r for r in rows if r["index"] == idx]
        assert len(x) == 1
        assert x[0]["current_status"] == "DATA_BLOCKED"
        assert x[0]["historical_status"] == "DATA_BLOCKED_NO_INTERVAL_FILE"
        assert x[0]["ticker"] == ""


def test_snapshot_p8_and_paper_separation():
    s = json.loads((ROOT / "dashboard/data/invest_terminal_data.json").read_text(encoding="utf-8"))
    assert s["p8"]["status"] == "P8_FIRST_ROUND_NO_GO"
    assert s["account"]["account_id"] == "PAPER-50000"
    assert "PAPER-50000" not in json.dumps(s["p8"])


def test_p8_audit_identifies_price_contamination():
    a = json.loads((P8 / "p8_audit.json").read_text(encoding="utf-8"))
    assert a["status"] == "AUDIT_COMPLETE_DATA_ISSUE_IDENTIFIED"
    assert a["data_issue"]["excluded_count"] == 109
    assert "CBE" in a["data_issue"]["excluded_tickers"]
    assert "ACS" in a["data_issue"]["excluded_tickers"]
    assert a["original_vs_corrected"]["MOMENTUM_120"]["corrected_cagr"] < a["original_vs_corrected"]["MOMENTUM_120"]["original_cagr"]


def test_walk_forward_is_complete_and_no_go():
    w = json.loads((P8 / "walk_forward_results.json").read_text(encoding="utf-8"))
    assert w["status"] == "WALK_FORWARD_COMPLETE"
    assert len(w["windows"]) == 19
    assert w["selected_strategy"]["max_drawdown"] < -0.35
    s = json.loads((P8 / "p8_status.json").read_text(encoding="utf-8"))
    assert s["walk_forward"]["gate"] == "NO-GO"
    assert s["audit"]["data_issue"]["excluded_count"] == 109
