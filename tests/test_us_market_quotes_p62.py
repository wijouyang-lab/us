import csv
import json
from pathlib import Path
import pandas as pd
from tools.research.audit_us_market_quotes_p62 import (
    COL_CODE, COL_NAME, COL_PRICE, COL_CAP, COL_PE,
    build_spot_index, match_one, norm, run,
)

UNIVERSE = Path("data/universe/us_equities_current.csv")


def spot(rows):
    return pd.DataFrame([{COL_CODE: c, COL_NAME: n, COL_PRICE: p, COL_CAP: cap, COL_PE: pe}
                         for c, n, p, cap, pe in rows])


def test_norm_handles_dots_hyphens_and_class_shares():
    assert norm("BRK.B") == "BRKB"
    assert norm("BRK-B") == "BRKB"
    assert norm("BRK_B") == "BRKB"
    assert norm("GOOGL") != norm("GOOG")


def test_spot_index_and_brk_b_mapping():
    idx = build_spot_index(spot([("106.BRK_B", "Berkshire Hathaway", 500, 1e12, 10)]))
    status, chosen, _ = match_one("BRK.B", "Berkshire Hathaway Inc. Common Stock", "NYSE", idx)
    assert status == "QUOTE_MATCHED" and chosen["vendor_symbol"] == "106.BRK_B"


def test_single_missing_price_is_invalid_not_not_found():
    idx = build_spot_index(spot([("105.XYZ", "XYZ Corp", None, None, None)]))
    status, _, _ = match_one("XYZ", "XYZ Corp - Common Stock", "NASDAQ", idx)
    assert status == "INVALID_QUOTE"


def test_ambiguous_ticker_not_merged_without_name_evidence():
    idx = build_spot_index(spot([
        ("105.ABC", "Alpha Corp", 10, 1e9, 10),
        ("106.ABC", "Beta Corp", 20, 2e9, 20),
    ]))
    status, _, candidates = match_one("ABC", "Gamma Holdings", "NYSE", idx)
    assert status == "AMBIGUOUS_MATCH" and len(candidates) == 2


def test_name_can_disambiguate_same_ticker():
    idx = build_spot_index(spot([
        ("105.ABC", "Alpha Corp", 10, 1e9, 10),
        ("106.ABC", "Beta Corp", 20, 2e9, 20),
    ]))
    status, chosen, _ = match_one("ABC", "Alpha Corp - Common Stock", "NASDAQ", idx)
    assert status == "QUOTE_MATCHED" and chosen["vendor_symbol"] == "105.ABC"


def test_source_error_marks_all_targets_and_preserves_unclassified(tmp_path):
    report = run(None, out_json=tmp_path / "j.json", out_map=tmp_path / "m.csv",
                 out_fail=tmp_path / "f.csv", source_error="Push2RateLimitError")
    assert report["summary"]["target_total"] == 5502
    assert report["summary"]["source_error"] == 5502
    assert report["summary"]["unclassified_total"] == 113
    assert report["summary"]["matched"] == 0


def test_universe_denominator_and_cohorts():
    with UNIVERSE.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    common = [r for r in rows if r["security_type"] == "COMMON"]
    adr = [r for r in rows if r["security_type"] == "ADR"]
    unclassified = [r for r in rows if r["security_type"] == "UNCLASSIFIED"]
    assert len(common) + len(adr) == 5502
    assert len(unclassified) == 113
