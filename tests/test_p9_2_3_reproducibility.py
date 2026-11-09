import csv, json
from pathlib import Path
from tools.research.p9_2_3.reproducibility import MiniLedger

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/research/p9_2_3_reproducibility"


def load(name): return json.loads((P / name).read_text(encoding="utf-8"))


def test_p91_not_reproducible():
    s = load("reproducibility_audit.json")
    assert s["p9_1"]["status"] == "P9_1_ORIGINAL_RESULT_NOT_REPRODUCIBLE"
    assert "price" in s["p9_1"]["reason"].lower()


def test_independent_nav_reconciliation_passes():
    rows = list(csv.DictReader((P / "ledger_independent_reconciliation.csv").open(encoding="utf-8")))
    assert len(rows) == 8
    assert max(float(r["max_abs_nav_diff"]) for r in rows) < 1e-8
    assert all(int(r["unmatched_sells"]) == 0 for r in rows)


def test_manifest_has_required_fields_and_hashes():
    m = load("run_manifest_example.json")
    req = {"experiment_id","strategy_id","git_commit_sha","git_dirty_status","source_diff_hash","python_version","dependency_lock_hash","data_sources","cost_model_version","parameters","start_date","end_date","calendar","timezone","execution_rule","command","random_seed","initial_capital","outputs","status"}
    assert req <= set(m)
    assert len(m["git_commit_sha"]) == 40
    assert m["data_sources"] and all(len(v["sha256"]) == 64 for v in m["data_sources"].values())
    assert m["outputs"] and all(len(v["sha256"]) == 64 for v in m["outputs"].values())


def test_manifest_schema_exists_and_required_outputs():
    schema = load("run_manifest.schema.json")
    assert "required" in schema
    audit = load("reproducibility_audit.json")
    assert "run_manifest.json" in audit["framework"]["required_outputs"]
    assert audit["no_shadow"] is True


def test_mini_ledger_partial_sell_and_open_position():
    led = MiniLedger(50000)
    led.buy("ABC", 100, 10.0, 10.01, fee=1.0)
    assert led.pos["ABC"] == 100
    led.sell("ABC", 40, 11.0, 10.99, fee=1.0)
    assert led.pos["ABC"] == 60
    nav = led.nav({"ABC": 12.0})
    # cash = 50000 - 1001 - 1 + 40*10.99 - 1 = 49436; stock = 720
    assert abs(nav - (49436.6 + 720.0)) < 1e-9
    led.sell("ABC", 60, 12.0, 11.99, fee=1.0)
    assert led.pos["ABC"] == 0


def test_mini_ledger_unmatched_sell_raises():
    led = MiniLedger()
    try:
        led.sell("ABC", 1, 10, 10)
    except ValueError:
        return
    raise AssertionError("expected unmatched sell error")
