import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/research/p8_4_market_neutral_alpha"


def load(name): return json.loads((P / name).read_text(encoding="utf-8"))


def test_audits_exist_and_thresholds_are_sensitivity():
    t = list(csv.DictReader((P / "eligibility_filter_audit.csv").open(encoding="utf-8")))
    assert [float(x["threshold_x"]) for x in t] == [3.0, 5.0, 10.0]
    assert all(x["gme_days"] == "0" for x in t)
    assert (P / "label_missingness_audit.csv").exists()
    assert (P / "label_missing_by_volatility.csv").exists()
    d = load("coverage_denominator_audit.json")
    assert d["all_member_days"] == 1095490
    assert d["p83_panel_rows"] == 352036


def test_residual_factor_count_and_bh_family():
    d = load("factor_definitions.json")
    assert len(d) == 7
    assert set(d) >= {"RESID_MOM_252","RESID_REV_5","RESID_REV_20","IDIO_VOL_60","DOWNSIDE_IDIO_60","RESID_TREND_PERSIST_60","BETA_ADJ_MOM_60"}
    rows = list(csv.DictReader((P / "factor_ic_results.csv").open(encoding="utf-8")))
    assert len(rows) == 21
    bh = list(csv.DictReader((P / "factor_bh_results.csv").open(encoding="utf-8")))
    assert len(bh) == 78
    assert all(float(r["bh_q"]) > 0.10 for r in bh if r["kind"] != "FAMA_MACBETH")


def test_no_candidate_or_shadow():
    s = load("p8_4_status.json")
    assert s["status"] == "P8_4_NO_GO"
    assert s["go_count"] == 0
    assert s["no_shadow"] is True
    c = list(csv.DictReader((P / "strategy_candidates.csv").open(encoding="utf-8")))
    assert c == []


def test_regime_and_robustness_outputs():
    r = list(csv.DictReader((P / "factor_regime_results.csv").open(encoding="utf-8")))
    assert len(r) == 36
    assert all("bh_q_all" in x for x in r)
    assert (P / "factor_fama_macbeth.csv").exists()
    assert (P / "factor_robustness.csv").exists()
    assert (P / "factor_correlation.csv").exists()


def test_snapshot_p8_4():
    s = json.loads((ROOT / "dashboard/data/invest_terminal_data.json").read_text(encoding="utf-8"))
    assert s["p8_4"]["status"] == "P8_4_NO_GO"
    assert s["p8_4"]["go_count"] == 0
    assert s["account"]["account_id"] == "PAPER-50000"
    assert "RESEARCH_SHADOW_P8" not in json.dumps(s)
