import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/research/p11_2"


def _rows(name):
    return list(csv.DictReader((DATA / name).open(encoding="utf-8")))


def test_factor_results_shape_and_family():
    rows = _rows("p11_2_factor_results.csv")
    assert len(rows) == 60
    assert len({r["factor"] for r in rows}) == 20
    assert {int(r["horizon"]) for r in rows} == {5, 10, 20}


def test_no_positive_tradeable_alpha_claim():
    rows = _rows("p11_2_factor_results.csv")
    assert max(float(r["net_top10"]) for r in rows) < 0.01
    assert max(float(r["mean_ic"]) for r in rows) < 0.01
    sig = [r for r in rows if float(r["bh_q"]) < 0.05]
    assert len(sig) == 2
    assert all(r["factor"] == "mom5" and float(r["mean_ic"]) < 0 for r in sig)


def test_oos_has_no_economic_signal():
    rows = _rows("p11_2_annual_ic.csv")
    oos = [r for r in rows if r["period"] == "oos"]
    assert oos
    assert max(float(r["mean_ic"]) for r in oos) < 0.01
    assert min(float(r["mean_ic"]) for r in oos) > -0.03


def test_quintile_and_correlation_outputs():
    q = _rows("p11_2_quintile_returns.csv")
    assert len(q) == 60
    assert set(q[0]) >= {"factor", "horizon", "q1", "q2", "q3", "q4", "q5"}
    corr = _rows("p11_2_factor_correlation.csv")
    assert len(corr) == 20


def test_config_locks_design_and_costs():
    c = json.loads((DATA / "p11_2_experiment_config.json").read_text(encoding="utf-8"))
    assert c["cost_bps_roundtrip"] == 20.0
    assert c["synthetic"] is False
    assert c["horizons"] == [5, 10, 20]
    assert len(c["factors"]) == 20
    assert "SPY" in c["benchmark"]


def test_report_is_no_go_and_no_raw_data():
    doc = (ROOT / "docs/research/P11_2_PRICE_FACTOR_STUDY.md").read_text(encoding="utf-8")
    assert "P11_2_STATUS: NO-GO" in doc
    assert "TRADEABLE_ALPHA: NO" in doc
    assert "PORTFOLIO_CONSTRUCTION_READY: NO" in doc
    assert "ALL 8 NO-GO" in doc
    assert not list(DATA.glob("*.parquet"))
    assert not list(DATA.glob("*.pkl"))
