import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/research/p9_2_2_ledger"


def load(name): return json.loads((P / name).read_text(encoding="utf-8"))


def test_ledger_fields_and_two_sided_costs():
    rows = list(csv.DictReader((P / "trade_ledger_final.csv").open(encoding="utf-8")))
    assert rows
    assert {r["side"] for r in rows} == {"BUY", "SELL"}
    assert all({"reference_price","execution_price","fees_only","slippage_cost","all_in_execution_cost","position_before","position_after"} <= set(r) for r in rows)
    assert all(float(r["fees_only"]) >= 0 for r in rows)


def test_daily_nav_identity_and_open_positions():
    d = list(csv.DictReader((P / "daily_nav_reconciliation.csv").open(encoding="utf-8")))
    assert d
    assert max(abs(float(r["nav_identity_delta"])) for r in d) < 1e-6
    o = list(csv.DictReader((P / "open_positions_final.csv").open(encoding="utf-8")))
    assert o
    assert all(int(r["shares"]) > 0 for r in o)


def test_reconciliation_is_partial_not_claimed_exact():
    s = load("p9_2_2_ledger_status.json")
    assert s["status"] == "P9_2_2_LEDGER_PARTIAL"
    assert s["p9_1_metric_restatement"] is False
    assert s["no_shadow"] is True
    assert "DATA_BLOCKED" in s["reason"]


def test_all_in_equals_fees_plus_slippage():
    rows = list(csv.DictReader((P / "trade_ledger_final.csv").open(encoding="utf-8")))
    assert all(abs(float(r["all_in_execution_cost"]) - (float(r["fees_only"]) + float(r["slippage_cost"]))) < 1e-6 for r in rows)
