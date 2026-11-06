import csv, json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P7 = ROOT / "data/universe/p7"


def rows(name):
    with (P7 / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load(name):
    return json.loads((P7 / name).read_text(encoding="utf-8"))


def test_four_strategies_and_value_launchable():
    s = load("p7_status.json")
    assert s["status"] == "P7_RESEARCH_READY"
    assert s["research_only"] is True
    assert set(s["strategies"]) == {"VALUE_V1", "QUALITY_V1", "GARP_V1", "BLENDED_V1"}
    assert s["strategies"]["VALUE_V1"]["launchable"] is True
    assert s["strategies"]["VALUE_V1"]["candidate_count"] >= 10
    for k in ("QUALITY_V1", "GARP_V1", "BLENDED_V1"):
        assert s["strategies"][k]["launchable"] is False
        assert s["strategies"][k]["status"] == "NOT_LAUNCHABLE"


def test_portfolio_constraints_and_cash():
    w = rows("portfolio_weights.csv")
    assert w
    by_variant = defaultdict(list)
    for r in w:
        by_variant[(r["strategy"], r["variant"])].append(r)
    for key, rs in by_variant.items():
        total = sum(float(r["weight"]) for r in rs)
        assert abs(total - 0.95) < 1e-6
        assert max(float(r["weight"]) for r in rs) <= 0.10 + 1e-9
        sec = defaultdict(float)
        for r in rs:
            sec[r["model_family"]] += float(r["weight"])
        assert max(sec.values()) <= 0.25 + 1e-9


def test_missing_factor_is_not_zero_filled():
    scores = rows("strategy_scores.csv")
    for r in scores:
        present = [x for x in r["factors_present"].split("|") if x]
        assert int(r["factor_count"]) == len(present)
        if r["factor_count"] == "0":
            assert r["blended_score"] == ""
    cand = rows("strategy_candidates.csv")
    for r in cand:
        if r["strategy"] == "BLENDED_V1":
            assert int(r["factor_count"]) >= 2


def test_shadow_is_independent_and_pending():
    s = load("p7_status.json")
    sh = s["shadow"]
    assert sh["shadow_id"] == "RESEARCH_SHADOW_P7"
    assert sh["paper_account_untouched"] is True
    assert sh["paper_account_read"] is False and sh["paper_account_write"] is False
    assert sh["execution_status"] == "PENDING_NEXT_SESSION"
    assert sh["next_tradable_session"] == "2026-11-06"
    nav = rows("shadow_nav.csv")
    assert nav[0]["nav"] == "50000.0" and nav[0]["positions_value"] == "0.0"
    assert nav[0]["status"] == "PENDING_NEXT_SESSION"
    pos = rows("shadow_positions.csv")
    assert pos and all(r["status"] == "PENDING_NEXT_SESSION" for r in pos)
    assert all(r["fill_price"] == "" for r in pos)
    assert "PAPER-50000" not in load("p7_status.json").get("source", "")


def test_updated_fundamentals_and_benchmarks():
    u = rows("updated_fundamentals.csv")
    assert len(u) == 94
    assert any(r["refresh_status"] == "UPDATED_FROM_SEC_COMPANYFACTS" for r in u)
    assert any(r["refresh_status"] == "SIX_K_QUARANTINED" for r in u)
    b = rows("benchmark_snapshot.csv")
    assert {r["ticker"] for r in b} >= {"SPY", "QQQ", "IWM"}
    assert all(r["date"] <= "2026-11-05" for r in b if r["date"])
    assert any(r["ticker"] == "EQUAL_WEIGHT" for r in b)


def test_snapshot_contains_p7_and_remains_paper_separate():
    s = json.loads((ROOT / "dashboard/data/invest_terminal_data.json").read_text(encoding="utf-8"))
    assert s["p7"]["status"] == "P7_RESEARCH_READY"
    assert s["p7"]["shadow"]["paper_account_untouched"] is True
    assert s["account"]["account_id"] == "PAPER-50000"
    assert s["p7"]["shadow"]["shadow_id"] != s["account"]["account_id"]
