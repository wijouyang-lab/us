import csv, json
from datetime import date
from pathlib import Path
from tools.research.rebuild_quality_pit_history_p67 import visible_latest, membership_events, price_on_or_before, norm
from tools.research.evaluate_quality_forward_returns_p67 import newey_west_tstat, bh_qvalues

OUT = Path("data/research")


def test_visible_latest_respects_filed_and_period():
    recs = [
        {"value": 1, "end": date(2024,12,31), "filed": date(2025,2,1), "accn": "a"},
        {"value": 2, "end": date(2024,12,31), "filed": date(2025,3,1), "accn": "b"},
        {"value": 9, "end": date(2025,12,31), "filed": date(2026,2,1), "accn": "future"},
    ]
    x = visible_latest(recs, date(2025,6,1))
    assert x["value"] == 2 and x["accn"] == "b"
    y = visible_latest(recs, date(2025,2,15))
    assert y["value"] == 1


def test_membership_respects_added_and_removed(tmp_path):
    p = tmp_path / "comp.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["symbol","cik","date_added","date_removed"]); w.writeheader()
        w.writerows([
            {"symbol":"AAA","cik":"1","date_added":"2016-01-01","date_removed":"2020-01-01"},
            {"symbol":"BBB","cik":"2","date_added":"2018-01-01","date_removed":""},
        ])
    rows = membership_events(p, Path("does_not_exist.csv"))
    assert rows[0]["removed"] == date(2020,1,1)
    assert rows[1]["removed"] is None


def test_price_on_or_before_uses_adjusted_close(tmp_path):
    import pandas as pd
    df = pd.DataFrame({"Date":[date(2020,1,2),date(2020,1,3)],"Ticker":["AAA","AAA"],"Close":[10.0,11.0]})
    s = df
    r = price_on_or_before(s, date(2020,1,3))
    assert r["Close"] == 11.0
    assert price_on_or_before(s, date(2020,1,20)) is None


def test_newey_west_is_reproducible_and_has_lags():
    x = [0.1, 0.2, -0.1, 0.3, 0.15, 0.05]
    a = newey_west_tstat(x); b = newey_west_tstat(x)
    assert a == b
    assert a["n"] == 6 and a["lags"] >= 1
    assert a["tstat"] is not None


def test_benjamini_hochberg_is_monotone_and_bounded():
    q = bh_qvalues([0.01, 0.04, 0.03, 0.2])
    assert all(0 <= v <= 1 for v in q)
    assert min(q) <= max(q)


def test_gate_fails_and_no_forward_test():
    c = json.loads((OUT / "quality_pit_coverage_p67.json").read_text())
    f = json.loads((OUT / "quality_forward_return_tests_p67.json").read_text())
    assert c["gates"]["backtest_ready"] is False
    assert c["membership"]["member_session_coverage"] < 0.95
    assert c["membership"]["ticker_coverage"] < 0.98
    assert f["status"] == "BLOCKED_BY_HISTORICAL_PIT_GATE"
    assert f["tests"] == []


def test_actual_historical_panel_counts():
    c = json.loads((OUT / "quality_pit_coverage_p67.json").read_text())
    s = json.loads((OUT / "quality_historical_stability_p67.json").read_text())
    assert c["financial"]["historical_quarters"] == 43
    assert c["financial"]["candidates_with_2_netincome"] == 3130
    assert s["period"]["scored_quarters"] == 37
    assert s["period"]["observations"] == 58396
    assert s["period"]["unique_issuers"] == 2536
    assert s["long_horizon_first_last_year_spearman"] is not None
