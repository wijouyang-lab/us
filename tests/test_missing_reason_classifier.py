# -*- coding: utf-8 -*-
"""Tests for missing-member reason classification."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import missing_reason_classifier as c  # noqa: E402


def test_current_ticker_not_delisted():
    out = c.classify({"ticker": "MUR", "cik": "1", "sec_name": "MURPHY OIL",
                      "tickers": ["MUR"], "delisting_forms": []})
    assert out["category"] == c.STILL
    assert out["lifecycle_status"] == "LISTED_UNDER_ORIGINAL_TICKER"


def test_index_removal_is_not_delisting_without_form():
    out = c.classify({"ticker": "AN", "cik": "1", "sec_name": "AUTONATION",
                      "tickers": ["AN"], "delisting_forms": []})
    assert out["category"] == c.STILL


def test_rename_is_not_new_company():
    out = c.classify({"ticker": "ABC", "cik": "1", "sec_name": "Cencora",
                      "tickers": ["COR"], "delisting_forms": []})
    assert out["category"] == c.CHANGED
    assert out["identity_status"] == "CIK_CONFIRMED"


def test_empty_ticker_with_form_is_delisted():
    out = c.classify({"ticker": "AET", "cik": "1", "sec_name": "AETNA",
                      "tickers": [], "delisting_forms": [{"form": "25-NSE", "date": "2018-11-29"}]})
    assert out["category"] == c.DELISTED


def test_missing_cik_is_unresolved():
    out = c.classify({"ticker": "XYZ", "tickers": ["XYZ"]})
    assert out["category"] == c.UNRESOLVED
    assert out["identity_status"] == "UNVERIFIED"


def test_reuse_requires_evidence_flag():
    out = c.classify({"ticker": "STI", "cik": "1", "sec_name": "SUNTRUST",
                      "tickers": [], "delisting_forms": [{"form": "25-NSE"}],
                      "reuse_suspected": True})
    assert out["category"] == c.REUSE
    assert out["recovery_status"] == "TICKER_REUSE_HIGH_RISK"
def test_v2_has_all_categories_and_preserves_unknowns():
    import pandas as pd
    d = pd.read_csv("docs/research/missing_202_reason_classification_v2_2026-10-29.csv")
    assert len(d) == 202
    assert d.classification.value_counts().to_dict() == {
        "HISTORICAL_MEMBERSHIP_ONLY": 176,
        "DELISTED_OR_ACQUIRED": 10,
        "STILL_TRADING": 8,
        "TICKER_OR_NAME_CHANGED": 6,
        "TICKER_REUSE_SUSPECTED": 2,
    }
    assert (d[d.ticker == "AN"].classification == "STILL_TRADING").all()
    assert (d[d.ticker == "AIV"].classification == "STILL_TRADING").all()
    assert (d[d.ticker == "AET"].classification == "DELISTED_OR_ACQUIRED").all()
    assert (d[d.ticker == "ABC"].classification == "TICKER_OR_NAME_CHANGED").all()
    assert (d.price_status == "NO_SERIES_IN_CURRENT_PANEL").all()
def test_v3_batch2_categories():
    import pandas as pd
    d = pd.read_csv("docs/research/missing_202_reason_classification_v3_2026-10-29.csv")
    assert len(d) == 202
    assert d.classification.value_counts().to_dict() == {
        "HISTORICAL_MEMBERSHIP_ONLY": 153,
        "DELISTED_OR_ACQUIRED": 18,
        "STILL_TRADING": 17,
        "TICKER_OR_NAME_CHANGED": 11,
        "TICKER_REUSE_SUSPECTED": 2,
        "IDENTITY_UNRESOLVED": 1,
    }
    assert (d[d.ticker == "FLT"].classification == "TICKER_OR_NAME_CHANGED").all()
    assert (d[d.ticker == "FRC"].classification == "IDENTITY_UNRESOLVED").all()
    assert (d[d.ticker == "DXC"].classification == "STILL_TRADING").all()
def test_v4_batch3_counts_and_overrides():
    import pandas as pd
    d = pd.read_csv("docs/research/missing_202_reason_classification_v4_2026-10-29.csv")
    assert len(d) == 202
    assert d.classification.value_counts().to_dict() == {
        "HISTORICAL_MEMBERSHIP_ONLY": 129,
        "STILL_TRADING": 33,
        "DELISTED_OR_ACQUIRED": 23,
        "TICKER_OR_NAME_CHANGED": 14,
        "TICKER_REUSE_SUSPECTED": 2,
        "IDENTITY_UNRESOLVED": 1,
    }
    assert (d[d.ticker == "FI"].classification == "TICKER_OR_NAME_CHANGED").all()
    assert (d[d.ticker == "CTRA"].classification == "DELISTED_OR_ACQUIRED").all()
    assert (d[d.ticker == "CTLT"].classification == "DELISTED_OR_ACQUIRED").all()
    assert (d[d.ticker == "RVTY"].classification == "TICKER_OR_NAME_CHANGED").all()
    assert not d.ticker.duplicated().any()
def test_v5_batch4_counts():
    import pandas as pd
    d = pd.read_csv("docs/research/missing_202_reason_classification_v5_2026-10-29.csv")
    assert len(d) == 202
    assert d.classification.value_counts().to_dict() == {
        "HISTORICAL_MEMBERSHIP_ONLY": 104,
        "DELISTED_OR_ACQUIRED": 42,
        "STILL_TRADING": 33,
        "TICKER_OR_NAME_CHANGED": 20,
        "TICKER_REUSE_SUSPECTED": 2,
        "IDENTITY_UNRESOLVED": 1,
    }
    assert (d[d.ticker == "FB"].classification == "TICKER_OR_NAME_CHANGED").all()
    assert (d[d.ticker == "COL"].classification == "DELISTED_OR_ACQUIRED").all()
    assert (d[d.ticker == "DISCA"].classification == "TICKER_OR_NAME_CHANGED").all()
    assert not d.ticker.duplicated().any()
def test_v6_batch5_counts():
    import pandas as pd
    d = pd.read_csv("docs/research/missing_202_reason_classification_v6_2026-10-29.csv")
    assert len(d) == 202
    assert d.classification.value_counts().to_dict() == {
        "HISTORICAL_MEMBERSHIP_ONLY": 79,
        "DELISTED_OR_ACQUIRED": 59,
        "STILL_TRADING": 39,
        "TICKER_OR_NAME_CHANGED": 22,
        "TICKER_REUSE_SUSPECTED": 2,
        "IDENTITY_UNRESOLVED": 1,
    }
    assert (d[d.ticker == "KORS"].classification == "TICKER_OR_NAME_CHANGED").all()
    assert (d[d.ticker == "PBI"].classification == "STILL_TRADING").all()
    assert (d[d.ticker == "LLTC"].classification == "DELISTED_OR_ACQUIRED").all()
    assert not d.ticker.duplicated().any()
def test_v7_batch6_counts():
    import pandas as pd
    d = pd.read_csv("docs/research/missing_202_reason_classification_v7_2026-10-29.csv")
    assert len(d) == 202
    assert d.classification.value_counts().to_dict() == {
        "DELISTED_OR_ACQUIRED": 69,
        "HISTORICAL_MEMBERSHIP_ONLY": 54,
        "STILL_TRADING": 46,
        "TICKER_OR_NAME_CHANGED": 30,
        "TICKER_REUSE_SUSPECTED": 2,
        "IDENTITY_UNRESOLVED": 1,
    }
    assert (d[d.ticker == "TWTR"].classification == "DELISTED_OR_ACQUIRED").all()
    assert (d[d.ticker == "FLR"].classification == "STILL_TRADING").all()
    assert (d[d.ticker == "HRS"].classification == "TICKER_OR_NAME_CHANGED").all()
    assert not d.ticker.duplicated().any()
def test_v8_batch7_counts():
    import pandas as pd
    d = pd.read_csv("docs/research/missing_202_reason_classification_v8_2026-10-29.csv")
    assert len(d) == 202
    assert d.classification.value_counts().to_dict() == {
        "DELISTED_OR_ACQUIRED": 73,
        "STILL_TRADING": 66,
        "TICKER_OR_NAME_CHANGED": 31,
        "HISTORICAL_MEMBERSHIP_ONLY": 29,
        "TICKER_REUSE_SUSPECTED": 2,
        "IDENTITY_UNRESOLVED": 1,
    }
    assert (d[d.ticker == "JWN"].classification == "DELISTED_OR_ACQUIRED").all()
    assert (d[d.ticker == "GPS"].classification == "TICKER_OR_NAME_CHANGED").all()
    assert (d[d.ticker == "HOG"].classification == "STILL_TRADING").all()
    assert not d.ticker.duplicated().any()
def test_v9_batch8_counts():
    import pandas as pd
    d = pd.read_csv("docs/research/missing_202_reason_classification_v9_2026-10-29.csv")
    assert len(d) == 202
    assert d.classification.value_counts().to_dict() == {
        "DELISTED_OR_ACQUIRED": 84,
        "STILL_TRADING": 78,
        "TICKER_OR_NAME_CHANGED": 33,
        "HISTORICAL_MEMBERSHIP_ONLY": 4,
        "TICKER_REUSE_SUSPECTED": 2,
        "IDENTITY_UNRESOLVED": 1,
    }
    assert (d[d.ticker == "EQR"].classification == "TICKER_OR_NAME_CHANGED").all()
    assert (d[d.ticker == "MMC"].classification == "TICKER_OR_NAME_CHANGED").all()
    assert (d[d.ticker == "RHI"].classification == "STILL_TRADING").all()
    assert set(d[d.classification == "HISTORICAL_MEMBERSHIP_ONLY"].ticker) == {"PSKY", "SOLS", "TAP", "TTD"}
def test_v10_completes_202_and_retains_metadata_only_flags():
    import pandas as pd
    d = pd.read_csv("docs/research/missing_202_reason_classification_v10_2026-10-29.csv")
    assert len(d) == 202
    assert d.ticker.duplicated().sum() == 0
    assert d.classification.value_counts().to_dict() == {
        "DELISTED_OR_ACQUIRED": 84,
        "STILL_TRADING": 81,
        "TICKER_OR_NAME_CHANGED": 34,
        "TICKER_REUSE_SUSPECTED": 2,
        "IDENTITY_UNRESOLVED": 1,
    }
    assert (d[d.ticker == "PSKY"].classification == "TICKER_OR_NAME_CHANGED").all()
    assert (d[d.ticker == "SOLS"].classification == "STILL_TRADING").all()
    assert (d[d.ticker == "TAP"].classification == "STILL_TRADING").all()
    assert (d[d.ticker == "TTD"].classification == "STILL_TRADING").all()


def test_quality_audit_has_no_mapping_errors():
    import pandas as pd
    q = pd.read_csv("docs/research/classification_quality_audit_2026-10-29.csv")
    assert len(q) == 202
    assert q.ticker.duplicated().sum() == 0
    errs = q.errors.fillna("")
    assert not errs.str.contains("still_but_old_ticker_missing|dead_or_changed_but_old_ticker_current|cik_mismatch|no_sec_record").any()
    assert (errs == "delisting_metadata_only_25nse").sum() == 32
