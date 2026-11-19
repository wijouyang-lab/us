import json
from pathlib import Path

import pandas as pd


def test_entry_trend_has_no_positive_ic():
    s = json.loads(Path("data/research/p16/p16_summary.json").read_text())
    assert s["entry"]["mean_ic"] < 0


def test_regime_reduces_drawdown_vs_same_exit():
    s = json.loads(Path("data/research/p16/p16_summary.json").read_text())["variants"]
    assert s["both_regime_10"]["max_dd"] > s["both_noreg_10"]["max_dd"]
    assert s["both_regime_10"]["avg_positions"] < 10


def test_cost_erodes_cagr_monotonically():
    s = json.loads(Path("data/research/p16/p16_summary.json").read_text())["variants"]
    assert s["both_regime_5"]["cagr"] > s["both_regime_10"]["cagr"] > s["both_regime_20"]["cagr"]


def test_drawdown_is_negative_and_includes_initial_nav():
    n = pd.read_csv("data/research/p16/p16_nav_both_regime_10.csv")
    assert n.nav.iloc[0] > 0
    assert n.dd.min() < 0
    assert n.dd.max() <= 0


def test_spy_benchmark_exists():
    b = json.loads(Path("data/research/p16/p16_benchmark.json").read_text())["spy_buyhold"]
    assert b["cagr"] > 0.1 and b["max_dd"] < 0


def test_no_variant_beats_spy_with_15pct_dd():
    s = json.loads(Path("data/research/p16/p16_summary.json").read_text())["variants"]
    b = json.loads(Path("data/research/p16/p16_benchmark.json").read_text())["spy_buyhold"]
    for v in s.values():
        if v["cagr"] >= b["cagr"]:
            assert v["max_dd"] <= -0.15
    assert all(v["max_dd"] < -0.15 for v in s.values())


def test_manifest_hashes():
    import hashlib
    m = json.loads(Path("data/research/p16/p16_manifest.json").read_text())
    for name, meta in m["outputs"].items():
        p = Path("data/research/p16") / name
        assert p.exists() and p.stat().st_size == meta["bytes"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == meta["sha256"]
