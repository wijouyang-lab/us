# -*- coding: utf-8 -*-
from pathlib import Path
import pytest
from tools.investment_research.dividend.evidence_registry import split_id
from tools.investment_research.dividend.split_audit import SplitEvidence, split_status, adjust_dps
from tools.investment_research.dividend.dividend_event_collector import normalize, dedupe


def ev(**kw):
    base=dict(ticker="X",cik="1",event_type="DECLARED",announcement_date="2025-05-01",
              source_url="https://www.sec.gov/Archives/x",source_type="SEC 8-K",
              evidence_sha256="a"*64)
    base.update(kw); return base


def test_ratio_convention_forward_and_reverse():
    assert SplitEvidence("X",4.0,"2020-08-28","2020-08-31","https://sec.gov/x","h").ratio==4.0
    assert SplitEvidence("X",0.1,"2020-01-01","2020-01-02","https://sec.gov/x","h").ratio==0.1


def test_unverified_status_not_split_confirmed():
    r=split_status("AAPL",[SplitEvidence("AAPL",4.0,"2020-08-28","2020-08-31","https://sec.gov/x","h")])
    assert r["status"]=="DPS_SPLIT_BASIS_UNVERIFIED"
    assert r["cagr_allowed"] is False


def test_no_split_record_is_not_no_split_verified():
    assert split_status("X",[])["status"]=="DPS_SPLIT_BASIS_UNVERIFIED"


def test_adjust_dps_uses_only_future_verified_splits():
    splits=[{"split_ratio":4.0,"effective_date":"2020-08-31","verification_status":"VERIFIED"},
            {"split_ratio":2.0,"effective_date":"2019-01-01","verification_status":"VERIFIED"}]
    r=adjust_dps(4.0,"2020-01-01",splits,"AS_DECLARED_AT_TIME")
    assert r["value"]==1.0 and r["applied_ratios"]==[4.0]


def test_already_adjusted_dps_not_adjusted_again():
    r=adjust_dps(1.0,"2020-01-01",[{"split_ratio":4.0,"effective_date":"2020-08-31","verification_status":"VERIFIED"}],"SPLIT_ADJUSTED")
    assert r["value"]==1.0 and r["status"]=="ALREADY_ADJUSTED"


def test_unknown_basis_blocks_adjustment():
    assert adjust_dps(1.0,"2020-01-01",[],"UNKNOWN")["value"] is None


def test_event_same_source_dedupes():
    a=normalize(ev()); b=normalize(ev())
    assert len(dedupe([a,b]))==1


def test_different_sources_same_event_dedupes_with_alternate():
    a=normalize(ev()); b=normalize(ev(source_url="https://www.sec.gov/Archives/y"))
    out=dedupe([a,b])
    assert len(out)==1 and out[0]["alternate_sources"]


def test_different_tickers_not_merged():
    assert len(dedupe([normalize(ev()), normalize(ev(ticker="Y"))]))==2


def test_unverified_cannot_be_verified_without_notes():
    r=normalize(ev(verification_status="VERIFIED"))
    assert r["verification_status"]=="PARTIALLY_VERIFIED"


def test_missing_ex_date_status():
    r=normalize(ev(event_type="EX_DATE",ex_date=None))
    assert r["ex_date_status"]=="EX_DATE_UNAVAILABLE"


def test_event_requires_source_and_hash():
    with pytest.raises(ValueError):
        normalize(ev(source_url=""))
    with pytest.raises(ValueError):
        normalize(ev(evidence_sha256=""))
