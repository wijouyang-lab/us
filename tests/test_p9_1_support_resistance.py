import csv, gzip, json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/research/p9_1_support_resistance"


def load(name): return json.loads((P / name).read_text(encoding="utf-8"))


def test_data_and_event_coverage():
    d = load("data_audit.json")
    assert d["member_days"] == 1095490
    assert d["valid_verified_tradable"] == 981362
    assert d["post_hoc_classification_used"] is False
    e = list(csv.DictReader((P / "event_results.csv").open(encoding="utf-8")))
    assert len(e) == 24
    assert {x["experiment"] for x in e} == {"A_LEVEL_TOUCH","B_PATTERN_ONLY","C_SUPPORT_PATTERN","D_C_MACD","E_C_KDJ","F_C_BOTH","G_LEVEL_ALL_PATTERNS","H_G_BOTH"}


def test_pivot_is_confirmed_and_signal_uses_past_levels():
    with gzip.open(P / "p9_1_signals.csv.gz", "rt", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["experiment"] == "C_SUPPORT_PATTERN"]
    assert rows
    for r in rows[:500]:
        assert r["support_touches"].isdigit() and int(r["support_touches"]) >= 2
        if r["pivot_low_date"]:
            assert date.fromisoformat(r["pivot_low_date"]) <= date.fromisoformat(r["date"])
        assert r["bull_engulf"] == "True" or r["morning_star"] == "True"


def test_events_are_not_zero_filled_and_have_nonoverlap():
    e = list(csv.DictReader((P / "event_results.csv").open(encoding="utf-8")))
    assert all(float(r["events"]) > 0 for r in e)
    assert all("nonoverlap_events" in r for r in e)
    assert any(int(r["nonoverlap_events"]) > 0 for r in e)


def test_portfolio_is_diagnostic_and_no_go():
    p = load("portfolio_results.json")
    assert p["strategy_stats"]["max_drawdown"] >= -0.15
    assert p["strategy_stats"]["cagr"] < p["benchmarks"]["20QQQ_80BIL"]["cagr"]
    assert p["gate"] == "NO-GO"
    assert p["trades"] > 0
    assert p["total_costs"] > 0


def test_no_shadow_and_empty_candidates():
    s = load("p9_1_status.json")
    assert s["status"] == "P9_1_NO_GO"
    assert s["no_shadow"] is True
    assert list(csv.DictReader((P / "strategy_candidates.csv").open(encoding="utf-8"))) == []


def test_bh_family_is_unique_and_aliases_match():
    e = list(csv.DictReader((P / "event_results.csv").open(encoding="utf-8")))
    st = load("p9_1_status.json")
    assert st["bh_family"] == 18
    assert st["duplicate_alias_cells"] == 6
    m = {(r["experiment"], int(r["horizon"])): r for r in e}
    for h in (5, 10, 20):
        assert float(m[("G_LEVEL_ALL_PATTERNS", h)]["bh_q"]) == float(m[("C_SUPPORT_PATTERN", h)]["bh_q"])
        assert float(m[("H_G_BOTH", h)]["bh_q"]) == float(m[("F_C_BOTH", h)]["bh_q"])
        assert float(m[("G_LEVEL_ALL_PATTERNS", h)]["nonoverlap_bh_q"]) == float(m[("C_SUPPORT_PATTERN", h)]["nonoverlap_bh_q"])


def test_status_matches_completed_diagnostics():
    s = load("p9_1_status.json")
    assert s["status"] == "P9_1_NO_GO"
    assert s.get("event_research_completed") is True
    assert s.get("portfolio_diagnostics_completed") is True
    assert len(s.get("portfolios", {})) == 8
    assert all(v.get("gate") == "NO-GO" for v in s["portfolios"].values())
    assert not any("portfolio not run" in str(x).lower() for x in s.get("data_blocked", []))
