import json
from pathlib import Path

import pandas as pd


def test_476_events():
    e = pd.read_csv("data/research/p12_5_4/m1_event_inventory.csv", dtype=str)
    assert len(e) == 476


def test_event_families():
    e = pd.read_csv("data/research/p12_5_4/m1_event_inventory.csv", dtype=str)
    assert set(e.event_type.unique()) == {"cpi", "employment"}


def test_52_tests():
    m = pd.read_csv("data/research/p12_5_4/m3_multiple_testing.csv")
    assert len(m) == 52


def test_min_q_fails():
    s = json.loads(Path("data/research/p12_5_4/p12_5_4_final_summary.json").read_text())
    assert s["min_q"] > 0.05


def test_payroll_top():
    s = json.loads(Path("data/research/p12_5_4/p12_5_4_final_summary.json").read_text())
    t = s["top"][0]
    assert t["feature"] == "ix_initial_payroll_change_beta_iwm"
    assert t["horizon"] == 20
    assert t["mean_spread"] < 0


def test_global_holm_payroll():
    m = pd.read_csv("data/research/p12_5_4/m3_multiple_testing.csv")
    r = m[(m.feature == "ix_initial_payroll_change_beta_iwm") & (m.horizon == 20)].iloc[0]
    assert r.p_holm_all > 0.05


def test_fomc_vol20():
    f = pd.read_csv("data/research/p12_5_4/m3_fomc_results.csv")
    r = f[(f.feature == "vol20_z") & (f.horizon == 20)].iloc[0]
    assert r.mean_spread > 0


def test_bootstrap_reps():
    b = pd.read_csv("data/research/p12_5_4/m3_block_bootstrap.csv")
    assert b.reps.eq(2000).all()


def test_status_no_go():
    s = json.loads(Path("data/research/p12_5_4/p12_5_4_final_summary.json").read_text())
    assert s["status"] == "NO_GO"


def test_manifest_hashes():
    import hashlib
    m = json.loads(Path("data/research/p12_5_4/p12_5_4_output_manifest.json").read_text())
    for name, meta in m["outputs"].items():
        p = Path("data/research/p12_5_4") / name
        assert p.exists() and p.stat().st_size == meta["bytes"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == meta["sha256"]
