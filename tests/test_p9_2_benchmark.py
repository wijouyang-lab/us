import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/research/p9_2_benchmark_audit"


def load(name): return json.loads((P / name).read_text(encoding="utf-8"))


def test_legacy_benchmark_is_reproduced_and_wrong():
    b = load("benchmark_rebuild.json")
    assert abs(b["p9_1_formula_result"]["cagr"] - 0.02083) < 0.0002
    assert abs(b["p9_1_formula_result"]["max_drawdown"] + 0.03793) < 0.0002
    assert b["variants"]["2024-12-31"]["D"]["cagr"] > 0.04
    assert b["variants"]["2024-12-31"]["D"]["max_drawdown"] < -0.10


def test_g_is_partial_not_exact():
    g = load("benchmark_rebuild.json")["g_comparison"]
    assert g["status"].startswith("PARTIAL")
    assert abs(g["delta_cagr"]) < 0.02


def test_corporate_action_audit():
    rows = list(csv.DictReader((P / "corporate_actions_audit.csv").open(encoding="utf-8")))
    d = {r["asset"]: r for r in rows}
    assert int(d["QQQ"]["dividends"]) > 0
    assert int(d["SPY"]["dividends"]) > 0
    assert int(d["BIL"]["dividends"]) > 0


def test_complete_event_table_has_all_24_and_ci():
    rows = list(csv.DictReader((P / "event_stats_complete.csv").open(encoding="utf-8")))
    assert len(rows) == 24
    assert all({"hac_t","p_value","bh_q","ci95_low","ci95_high","mean_excess_spy","mean_excess_bil","nonoverlap_events"} <= set(r) for r in rows)


def test_exposure_and_no_shadow():
    rows = list(csv.DictReader((P / "strategy_exposure_audit.csv").open(encoding="utf-8")))
    assert len(rows) >= 8
    assert all(float(r["avg_equity_exposure"]) < 0.20 for r in rows)
    s = load("p9_2_audit_status.json")
    assert s["status"] == "P9_2_BENCHMARK_CORRECTED_STRATEGY_NO_GO"
    assert s["strategy_still_no_go"] is True
    assert s["no_shadow"] is True
