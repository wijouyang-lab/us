import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/universe/selection"


def load(name):
    with (OUT / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_tradability_is_separate_and_adv_is_not_fabricated():
    s = json.loads((OUT / "tradability/tradability_summary.json").read_text(encoding="utf-8"))
    assert s["liquidity_source"].startswith("YFINANCE")
    assert "not trading approval" in s["note"].lower()
    assert s["value"]["eligible"] == 16
    assert s["quality"]["eligible"] == 36
    assert s["garp"]["eligible"] == 18
    rows = load("tradability/value_tradable_candidates.csv")
    assert rows and all(r["adv20_usd"] != "" and r["adv60_usd"] != "" for r in rows)
    assert all(r["valid_sessions_20"] == "20" and r["valid_sessions_60"] == "60" for r in rows)
    assert all(r["tradability_status"] in ("ELIGIBLE", "WATCH", "BLOCKED", "DATA_BLOCKED") for r in rows)


def test_tradability_does_not_change_fundamental_score():
    base = {r["cik"]: r["value_composite_experimental"] for r in load("value_top50.csv")}
    trad = load("tradability/value_tradable_candidates.csv")
    for r in trad:
        assert r["value_composite_experimental"] == base[r["cik"]]


def test_three_scenarios_are_recorded():
    s = json.loads((OUT / "tradability/tradability_summary.json").read_text(encoding="utf-8"))
    assert set(s["scenarios"]) == {"conservative", "balanced", "aggressive"}
    for name, x in s["scenarios"].items():
        assert x["min_adv"] > 0
        assert s["value"]["scenario_counts"][name]


def test_special_models_are_explicitly_blocked_or_reviewed():
    s = json.loads((OUT / "special_model_coverage.json").read_text(encoding="utf-8"))
    assert s["status"] == "SPECIAL_MODEL_REQUIRED_NOT_IMPLEMENTED"
    assert s["special_models"]["REIT"]["value_rows"] > 0
    assert "not available" in s["implementable"]["REIT"].lower()
