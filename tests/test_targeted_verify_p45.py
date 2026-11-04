# -*- coding: utf-8 -*-
from pathlib import Path
import pytest
from tools.investment_research.dividend.dividend_targeted_verify_p45 import parse_common, parse_preferred, ROOT

CAT_EX = ("Caterpillar Inc. Increases Dividend. On June 10, 2026, the Board voted to raise the quarterly dividend "
          "by 12 cents, an eight percent increase, to one dollar and sixty-three cents ($1.63) per share of common "
          "stock payable Aug. 19, 2026, to shareholders of record at the close of business July 20, 2026.")
CAT_8K = ("On June 10, 2026, the Board of Directors declared a quarterly cash dividend of $1.63 per share of "
          "Company common stock, payable on August 19, 2026 to shareholders of record at the close of business "
          "on July 20, 2026. The per share dividend of $1.63 is an increase of twelve cents from the previous "
          "quarterly dividend of $1.51 per share.")
BAC_EX = ("July 24, 2026 Bank of America Increases Common Stock Dividend 14% to $0.32 Per Share. The Board of "
          "Directors declared a regular quarterly cash dividend on common stock of $0.32 per share, up $0.04 "
          "from the prior quarter, an increase of 14%. The dividend is payable on September 25, 2026 to "
          "shareholders of record as of September 4, 2026. The Board also declared a regular quarterly cash "
          "dividend of $1.75 per share on the 7% Cumulative Redeemable Preferred Stock, Series B.")


def test_cat_parenthesized_amount():
    e = parse_common(CAT_EX, "CAT", "EXHIBIT")[0]
    assert e["declared_per_share"] == 1.63
    assert e["record_date"] == "2026-07-20" and e["payment_date"] == "2026-08-19"


def test_abbreviated_month():
    e = parse_common(CAT_EX, "CAT", "EXHIBIT")[0]
    assert e["payment_date"] == "2026-08-19"


def test_cat_previous_from_primary():
    e = parse_common(CAT_8K, "CAT", "PRIMARY")[0]
    assert e["previous_per_share"] == 1.51
    assert e["previous_per_share_status"] == "VERIFIED"
    assert e["source_type"] == "SEC Form 8-K"


def test_bac_cross_sentence_dates():
    e = parse_common(BAC_EX, "BAC", "EXHIBIT")[0]
    assert e["record_date"] == "2026-09-04" and e["payment_date"] == "2026-09-25"


def test_bac_preferred_separate():
    common = parse_common(BAC_EX, "BAC", "EXHIBIT")
    pref = parse_preferred(BAC_EX, "BAC", "EXHIBIT")
    assert common[0]["declared_per_share"] == 0.32
    assert pref[0]["declared_per_share"] == 1.75
    assert pref[0]["status"] == "PREFERRED_STOCK_EXCLUDED_FROM_COMMON_DIVIDEND"


def test_bac_previous_not_arithmetic():
    e = parse_common(BAC_EX, "BAC", "EXHIBIT")[0]
    assert e["previous_per_share"] is None
    assert e["previous_per_share_status"] == "NOT_DISCLOSED_IN_FILING"


def test_source_type_by_role():
    assert parse_common(BAC_EX, "BAC", "EXHIBIT")[0]["source_type"] == "SEC Exhibit 99.1"
    assert parse_common(CAT_8K, "CAT", "PRIMARY")[0]["source_type"] == "SEC Form 8-K"


def test_ex_date_never_inferred():
    e = parse_common(BAC_EX, "BAC", "EXHIBIT")[0]
    assert e["ex_date"] is None and e["ex_date_status"] == "NOT_DISCLOSED_IN_FILING"


def test_manifest_hashes_match_when_artifact_available():
    if not (ROOT / "manifest.json").exists():
        pytest.skip("smoke artifact not present")
    import hashlib, json
    m = json.loads((ROOT / "manifest.json").read_text())
    for t in m["targets"]:
        for key in ("detail", "primary_doc", "exhibit_doc"):
            d = t[key]; p = ROOT / t["ticker"] / t["accession"] / Path(d["path"]).name
            assert hashlib.sha256(p.read_bytes()).hexdigest() == d["sha256"]


def test_two_sources_retain_own_hashes():
    if not (ROOT / "manifest.json").exists():
        pytest.skip("smoke artifact not present")
    import json
    m = json.loads((ROOT / "manifest.json").read_text())
    for t in m["targets"]:
        assert t["primary_doc"]["sha256"] != t["exhibit_doc"]["sha256"]


def test_cat_increase_values():
    e = parse_common(CAT_EX, "CAT", "EXHIBIT")[0]
    assert e["increase_per_share"] == 0.12 and e["increase_pct"] == 8


def test_bac_increase_values_without_previous():
    e = parse_common(BAC_EX, "BAC", "EXHIBIT")[0]
    assert e["increase_per_share"] == 0.04 and e["increase_pct"] == 14
    assert e["previous_per_share"] is None
