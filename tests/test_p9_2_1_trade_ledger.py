import csv, json
from pathlib import Path
from tools.research.p9_2_1.ledger_audit import fifo_match

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/research/p9_2_1_trade_ledger"


def load(name): return json.loads((P / name).read_text(encoding="utf-8"))


def test_ledger_has_both_sides_and_costs():
    rows = list(csv.DictReader((P / "trade_ledger.csv").open(encoding="utf-8")))
    assert rows
    assert {r["side"] for r in rows} == {"BUY", "SELL"}
    assert all(float(r["total_transaction_cost"]) > 0 for r in rows)
    assert all({"commission","exchange_fee","regulatory_fee","slippage_cost","position_before","position_after"} <= set(r) for r in rows)


def test_round_trips_and_reconciliation():
    rts = list(csv.DictReader((P / "round_trip_trades.csv").open(encoding="utf-8")))
    assert rts
    assert all(float(r["buy_fee"]) >= 0 and float(r["sell_fee"]) > 0 for r in rts)
    rec = list(csv.DictReader((P / "trade_cost_reconciliation.csv").open(encoding="utf-8")))
    assert rec
    assert all(abs(float(r["reported_fee_delta"])) < 10 for r in rec)
    assert any(float(r["slippage_not_in_reported_costs"]) > 0 for r in rec)


def test_fifo_partial_and_unmatched():
    matches, unmatched, remaining = fifo_match([("d1", 100, "b1"), ("d2", 50, "b2")], [("d3", 120, "s1"), ("d4", 40, "s2")])
    assert [m["qty"] for m in matches] == [100, 20, 30]
    assert unmatched == 10
    assert remaining == []


def test_audit_status_no_shadow():
    s = load("trade_cost_audit.json")
    assert s["buy_and_sell_fees"] == "BOTH_CALCULATED"
    assert s["sell_fee_omission"] is False
    assert s["ledger_completeness"] == "PARTIAL"
    assert s["no_shadow"] is True
