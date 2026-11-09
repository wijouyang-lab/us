import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/research/p10_3_sec_xbrl_coverage"


def load(name): return json.loads((P / name).read_text(encoding="utf-8"))


def test_all_66_aapl_filings_are_classified():
    rows = list(csv.DictReader((P / "aapl_all_status.csv").open(encoding="utf-8")))
    assert len(rows) == 66
    counts = {}
    for r in rows: counts[r["status"]] = counts.get(r["status"], 0) + 1
    assert counts.get("INLINE_XBRL_PARSED") == 23
    assert counts.get("SEPARATE_XBRL_PARSED") == 40
    assert counts.get("ORIGINAL_FILE_NO_XBRL") == 3
    assert sum(counts.values()) == 66


def test_separate_xbrl_facts_have_periods():
    rows = list(csv.DictReader((P / "separate_xbrl_facts.csv").open(encoding="utf-8")))
    assert len(rows) > 1000
    assert any(r["period_start"] and r["period_end"] for r in rows)
    assert len({r["field"] for r in rows}) >= 15


def test_pit_is_acceptance_proxy_not_publication_verified():
    rows = list(csv.DictReader((P / "pit_time_audit.csv").open(encoding="utf-8")))
    assert len(rows) == 66
    assert all(r["availability_status"] == "PIT_ACCEPTANCE_PROXY" for r in rows)
    assert all(r["first_market_usable_A"] and r["first_market_usable_B"] for r in rows)
    assert all(not r["first_public_available_at"] for r in rows)


def test_not_strategy_ready_and_30_not_parsed():
    s = load("p10_3_status.json")
    assert s["status"] == "P10_3_SEC_XBRL_PARTIAL"
    assert s["strategy_ready"] is False
    rows = list(csv.DictReader((P / "cross_section_30_status.csv").open(encoding="utf-8")))
    assert len(rows) == 30
    assert all(r["accession_parse_status"] == "NOT_PARSED_IN_PILOT" for r in rows)
