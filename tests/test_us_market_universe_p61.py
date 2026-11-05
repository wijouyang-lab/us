import json
from pathlib import Path
from tools.research.build_us_market_universe import classify, norm_ticker, read_pipe, source_timestamp

OUT = Path("data/universe")


def test_classification_common_adr_and_exclusions():
    assert classify("Apple Inc. - Common Stock", "N", "N")[0] == "COMMON"
    assert classify("ATA Creativity Global - American Depositary Shares", "N", "N")[0] == "ADR"
    assert classify("Company 7% Preferred Stock", "N", "N") == ("EXCLUDED", "PREFERRED")
    assert classify("Company - Warrant", "N", "N") == ("EXCLUDED", "WARRANT")
    assert classify("Company - Units", "N", "N") == ("EXCLUDED", "UNIT")
    assert classify("Example ETF", "Y", "N")[0] == "EXCLUDED"
    assert classify("Example Test Issue", "N", "Y")[0] == "EXCLUDED"
    assert classify("Mystery Security", "N", "N")[0] == "UNCLASSIFIED"


def test_ticker_normalization_preserves_class():
    assert norm_ticker("BRK.B") == "BRK.B"
    assert norm_ticker("BRK-B") == "BRK.B"
    assert norm_ticker("GOOGL") == "GOOGL"


def test_pipe_source_footer_timestamp(tmp_path):
    p = tmp_path / "nasdaqlisted.txt"
    p.write_text("Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares\n"
                 "AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N\n"
                 "File Creation Time: 1104202612:11|||||||\n")
    rows, n, ts = read_pipe(p, "nasdaqlisted")
    assert n == 1 and rows[0]["ticker"] == "AAPL"
    assert ts["parsed"] == "2026-11-04T12:11"


def test_actual_universe_files_and_counts():
    audit = json.loads((OUT / "us_equities_universe_audit.json").read_text())
    c = audit["counts"]
    assert c["raw_records"] == 13275
    assert c["current_records"] == 5615
    assert c["common"] == 5187
    assert c["adr"] == 315
    assert c["unclassified"] == 113
    assert c["excluded"] == 7660
    assert c["sample_28_missing"] == 0
    assert c["sp500_matched"] == 502
    assert c["sp500_missing"] == 1
    assert c["sec_ambiguous"] == 0


def test_excluded_csv_has_no_common_or_adr():
    import csv
    with (OUT / "us_equities_excluded.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows
    assert all(r["security_type"] == "EXCLUDED" for r in rows)
    assert all(r["exclusion_reason"] for r in rows)


def test_current_csv_contains_all_28_sample_tickers():
    import csv
    with (OUT / "us_equities_current.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    tickers = {r["ticker"] for r in rows}
    for t in ("AAPL", "MSFT", "GOOGL", "NVDA", "BRK.B", "RIVN"):
        assert t in tickers


def test_multi_class_examples_not_merged():
    audit = json.loads((OUT / "us_equities_universe_audit.json").read_text())
    examples = audit["multi_class_examples"][0]
    by = {x["ticker"] for x in examples}
    assert {"GOOG", "GOOGL"}.issubset(by)
    assert "FOX" in by and "FOXA" in by
