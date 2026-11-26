import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P7 = ROOT / "data/universe/p7"


def rows(name):
    with (P7 / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_p71_value_scores_are_actually_versioned():
    s = json.loads((P7 / "p71_score_refresh_summary.json").read_text(encoding="utf-8"))
    assert s["updated_rows"] == 93
    assert s["value_rows"] == 5453
    assert s["value_ranked"] > 0
    assert s["quality_garp"] == "NOT_RECALCULATED_MISSING_ASSETS_OR_HISTORY"
    new = {r["ticker"]: r for r in rows("value_top50_p71.csv")}
    old = {r["ticker"]: r for r in csv.DictReader(open(ROOT / "data/universe/selection/value_top50.csv", encoding="utf-8"))}
    assert new and old
    assert "score_version" in next(iter(new.values()))
    comp = rows("value_score_comparison_p71.csv")
    assert any(r["changed"] == "True" for r in comp)


def test_shadow_persistent_no_duplicate_pending_nav():
    state = json.loads((P7 / "shadow_state.json").read_text(encoding="utf-8"))
    assert state["shadow_id"] == "RESEARCH_SHADOW_P7"
    assert state["paper_account_untouched"] is True
    assert state["paper_account_read"] is False and state["paper_account_write"] is False
    nav = rows("shadow_nav.csv")
    assert len(nav) == 1
    assert nav[0]["status"] == "PENDING_NEXT_SESSION"
    assert nav[0]["nav"] == "50000.0"
    assert nav[0]["positions_value"] == "0.0"
    # no fabricated fill or return
    assert rows("shadow_fills.csv") == []
    assert all(r["status"] == "PENDING_NEXT_SESSION" for r in rows("shadow_positions.csv"))
    assert all(r["fill_price"] == "" for r in rows("shadow_positions.csv"))


def test_benchmark_dates_align_to_shadow_dates():
    nav = rows("shadow_nav.csv")
    b = rows("benchmark_nav.csv")
    shadow_dates = {r["date"] for r in nav}
    b_dates = {r["date"] for r in b if r["ticker"] in ("SPY", "QQQ", "IWM")}
    assert shadow_dates <= b_dates
    assert all(r["date"] <= "2026-11-05" for r in b)


def test_shadow_has_no_paper_database_path_or_account_id():
    state = json.loads((P7 / "shadow_state.json").read_text(encoding="utf-8"))
    assert "PAPER-50000" not in json.dumps(state)
    assert state["initial_capital"] == 50000.0
    status = json.loads((P7 / "p7_status.json").read_text(encoding="utf-8"))
    assert status["research_only"] is True
    assert status["shadow"]["shadow_id"] != "PAPER-50000"


def test_p71_launchable_rule_is_not_relaxed():
    s = json.loads((P7 / "p7_status.json").read_text(encoding="utf-8"))
    assert s["strategies"]["VALUE_V1"]["launchable"] is True
    for k in ("QUALITY_V1", "GARP_V1", "BLENDED_V1"):
        assert s["strategies"][k]["launchable"] is False
