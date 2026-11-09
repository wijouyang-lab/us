import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/research/p10_2_sec_as_filed"


def load(name): return json.loads((P / name).read_text(encoding="utf-8"))


def test_aapl_index_has_accessions_and_trade_dates():
    rows = list(csv.DictReader((P / "aapl_filings_index.csv").open(encoding="utf-8")))
    assert len(rows) == 66
    assert all(r["accession"] and r["acceptance_datetime"] for r in rows)
    assert all(r["trade_available_date"] for r in rows)
    assert {r["form"] for r in rows} >= {"10-K", "10-Q", "10-K/A", "10-Q/A"}


def test_facts_are_accession_level_and_period_bound():
    rows = list(csv.DictReader((P / "aapl_as_filed_facts.csv").open(encoding="utf-8")))
    assert len(rows) > 1000
    assert all(r["accession"] and r["field"] for r in rows)
    assert any(r["period_start"] and r["period_end"] for r in rows)


def test_field_and_8k_coverage():
    fields = list(csv.DictReader((P / "field_coverage.csv").open(encoding="utf-8")))
    assert len(fields) >= 15
    k = list(csv.DictReader((P / "aapl_8k_index.csv").open(encoding="utf-8")))
    assert len(k) > 0
    assert all(r["accession"] and r["acceptanceDateTime"] for r in k)


def test_p10_2_is_partial_and_not_strategy_ready():
    s = load("p10_2_status.json")
    assert s["status"] == "P10_2_SEC_AS_FILED_PARTIAL"
    assert s["strategy_ready"] is False
    assert s["aapl"]["parsed"] < s["aapl"]["filings"]
    assert s["cross_section"]["metadata_only"] == 30
