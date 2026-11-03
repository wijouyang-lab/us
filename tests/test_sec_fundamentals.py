# -*- coding: utf-8 -*-
import json
from pathlib import Path
import pytest

from tools.investment_research.metrics import analyze
from tools.investment_research.sec.normalize import Fact, duration_days


def fact(concept, value, start, end, filed="2025-05-05", unit="USD", form="10-Q", acc="A1"):
    return Fact(cik="0000000001", taxonomy="us-gaap", concept=concept, unit=unit, value=value,
                start=start, end=end, filed=filed, form=form, accession=acc)


def base_facts():
    fs = []
    periods = [("2025-01-01", "2025-03-31"), ("2025-04-01", "2025-06-30"),
               ("2025-07-01", "2025-09-30"), ("2025-10-01", "2025-12-31")]
    for i, (s, e) in enumerate(periods):
        fs += [fact("RevenueFromContractWithCustomerExcludingAssessedTax", 100, s, e, "2025-05-05", acc=f"Q{i}"),
               fact("NetIncomeLoss", 10, s, e, "2025-05-05", acc=f"Q{i}"),
               fact("NetCashProvidedByUsedInOperatingActivities", 20, s, e, "2025-05-05", acc=f"Q{i}"),
               fact("PaymentsToAcquirePropertyPlantAndEquipment", 5, s, e, "2025-05-05", acc=f"Q{i}")]
    fs += [fact("StockholdersEquity", 200, None, "2025-12-31", instant=True) if False else
           Fact("0000000001", "us-gaap", "StockholdersEquity", "USD", 200, None, "2025-12-31",
                "2025-05-05", "10-Q", "B1"),
           Fact("0000000001", "us-gaap", "CashAndCashEquivalentsAtCarryingValue", "USD", 50, None,
                "2025-12-31", "2025-05-05", "10-Q", "B2"),
           Fact("0000000001", "us-gaap", "LongTermDebtNoncurrent", "USD", 100, None, "2025-12-31",
                "2025-05-05", "10-Q", "B3"),
           Fact("0000000001", "us-gaap", "ShortTermBorrowings", "USD", 20, None, "2025-12-31",
                "2025-05-05", "10-Q", "B4"),
           Fact("0000000001", "us-gaap", "CommonStockSharesOutstanding", "shares", 10, None,
                "2025-12-31", "2025-05-05", "10-Q", "B5")]
    return fs


def test_ttm_uses_four_quarters_and_fcf():
    a = analyze("TEST", "0000000001", base_facts(), as_of="2026-01-01", market_price=100, current_shares=10)
    assert a["value"]["revenue"]["value"] == 400
    assert a["value"]["free_cash_flow"]["value"] == 60
    assert a["value"]["pe_ttm"]["value"] == pytest.approx(25)
    assert a["value"]["pb"]["value"] == pytest.approx(5)


def test_asof_before_filing_returns_insufficient():
    a = analyze("TEST", "0000000001", base_facts(), as_of="2025-05-01")
    assert a["value"]["revenue"]["status"] == "INSUFFICIENT_DATA"


def test_amendment_does_not_overwrite_historic_asof():
    fs = base_facts()
    fs.append(fact("RevenueFromContractWithCustomerExcludingAssessedTax", 120,
                   "2025-01-01", "2025-03-31", "2025-08-05", acc="AMD"))
    old = analyze("TEST", "0000000001", fs, as_of="2025-06-01")
    new = analyze("TEST", "0000000001", fs, as_of="2025-09-01")
    assert old["value"]["revenue"]["value"] == 400
    assert new["value"]["revenue"]["value"] == 420


def test_negative_equity_is_not_applicable():
    fs = base_facts()
    fs = [x for x in fs if x.concept != "StockholdersEquity"]
    fs.append(Fact("0000000001", "us-gaap", "StockholdersEquity", "USD", -10, None,
                   "2025-12-31", "2025-05-05", "10-Q", "BN"))
    a = analyze("TEST", "0000000001", fs, as_of="2026-01-01")
    assert a["quality"]["roe"]["status"] == "NOT_APPLICABLE"
    assert a["quality"]["debt_to_equity"]["status"] == "NOT_APPLICABLE"


def test_zero_revenue_margin_not_applicable():
    fs = [x for x in base_facts() if x.concept != "RevenueFromContractWithCustomerExcludingAssessedTax"]
    fs.append(fact("RevenueFromContractWithCustomerExcludingAssessedTax", 0, "2025-01-01", "2025-03-31"))
    a = analyze("TEST", "0000000001", fs, as_of="2026-01-01")
    assert a["quality"]["gross_margin"]["status"] == "NOT_APPLICABLE"


def test_peg_is_blocked_without_forward_estimates():
    a = analyze("TEST", "0000000001", base_facts(), as_of="2026-01-01")
    assert a["garp"]["peg"]["status"] == "DATA_BLOCKED"


def test_price_metrics_blocked_without_market_inputs():
    a = analyze("TEST", "0000000001", base_facts(), as_of="2026-01-01")
    assert a["value"]["pe_ttm"]["status"] == "DATA_BLOCKED"
    assert a["value"]["margin_of_safety"]["status"] == "DATA_BLOCKED"


def test_live_sample_snapshot_is_complete_and_honest():
    import json
    d = json.loads(Path("docs/research/sec_fundamentals_snapshot.json").read_text())
    assert len(d) == 9
    assert all("value" in a for a in d.values())
    assert all(a["value"]["revenue"]["status"] == "OK" for a in d.values())
    assert all(a["value"]["pe_ttm"]["status"] == "DATA_BLOCKED" for a in d.values())
    assert all(a["garp"]["peg"]["status"] == "DATA_BLOCKED" for a in d.values())
    assert d["RIVN"]["value"]["net_income"]["value"] < 0


def test_sec_manifest_hashes_match():
    import hashlib, json
    m = json.loads(Path("docs/research/sec_fundamentals_manifest.json").read_text())
    for name, meta in m["files"].items():
        b = Path(name).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(b).hexdigest() == meta["sha256_normalized_lf"]
