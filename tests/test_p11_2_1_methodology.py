import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/research/p11_2_1"


def _rows(name):
    return list(csv.DictReader((DATA / name).open(encoding="utf-8")))


def test_results_have_20_factors_but_17_independent():
    rows = _rows("p11_2_1_factor_results.csv")
    assert len(rows) == 60
    assert len({r["factor"] for r in rows}) == 20
    catalog = _rows("p11_2_1_factor_catalog.csv")
    assert len(catalog) == 20
    assert sum(1 for r in catalog if r["independent"].lower() == "true") == 17
    assert {r["factor"] for r in catalog if r["duplicate_of"]} == {"rs20", "rs60", "rs120"}


def test_no_positive_bh_significant_factor_and_no_tradeable_alpha():
    rows = _rows("p11_2_1_factor_results.csv")
    sig = [r for r in rows if float(r["bh_q"]) < 0.05]
    assert len(sig) == 2
    assert all(r["factor"] == "mom5" and float(r["mean_ic"]) < 0 for r in sig)
    assert max(float(r["net_top10"]) for r in rows) < 0.01
    assert max(float(r["mean_ic"]) for r in rows) < 0.01


def test_sample_eligibility_and_raw_return_contract():
    c = json.loads((DATA / "p11_2_1_experiment_config.json").read_text(encoding="utf-8"))
    assert "Y not used for eligibility" in c["sample_selection"]
    assert "portfolio returns raw" in c["winsorization"]
    assert c["benchmark_fair_comparison"] is False
    assert c["cost_model"] == "SIMPLIFIED_20BPS_ROUNDTRIP_NOT_IBKR"
    assert c["independent_factors"] == 17
    rows = _rows("p11_2_1_factor_results.csv")
    assert all(float(r["return_coverage"]) > 0.95 for r in rows)


def test_nonoverlap_and_oos_outputs_exist():
    rows = _rows("p11_2_1_factor_results.csv")
    assert all(r["nonoverlap_n"] for r in rows)
    annual = _rows("p11_2_1_annual_ic.csv")
    assert {r["period"] for r in annual} == {"dev", "val", "oos"}
    oos = [r for r in annual if r["period"] == "oos"]
    assert max(float(r["mean_ic"]) for r in oos) < 0.01


def test_report_is_no_go_and_preserves_old_results():
    doc = (ROOT / "docs/research/P11_2_1_METHODOLOGY_CORRECTION.md").read_text(encoding="utf-8")
    assert "P11_2_1_STATUS: NO-GO" in doc
    assert "POSITIVE_TRADEABLE_ALPHA: NO" in doc
    assert "POSITIVE_BH_SIGNIFICANT_FACTORS: 0" in doc
    assert "BENCHMARK_FAIR: NO" in doc
    assert "ALL 8 NO-GO" in doc
    assert (ROOT / "data/research/p11_2/p11_2_factor_results.csv").exists()


def test_factor_correlation_marks_rs_duplicate_and_slope_distinct():
    rows = list(csv.DictReader((DATA / "p11_2_1_factor_correlation.csv").open(encoding="utf-8")))
    assert len(rows) == 20
    # The correlation file stores factors as columns; reload with index.
    import pandas as pd
    c = pd.read_csv(DATA / "p11_2_1_factor_correlation.csv", index_col=0)
    assert abs(c.loc["rs20", "mom20"] - 1.0) < 1e-9
    assert c.loc["slope20", "mom20"] < 0.99
