# -*- coding: utf-8 -*-
from tools.investment_research.sec.industry import classify_sic, industry_from_submissions


def test_software_sic():
    r=classify_sic(7372,"Services-Prepackaged Software")
    assert r["normalized_industry"]=="Software"


def test_bank_and_insurance_and_reit():
    assert classify_sic(6021,"National Commercial Banks")["normalized_industry"]=="Banking"
    assert classify_sic(6311,"Life Insurance")["normalized_industry"]=="Insurance"
    assert classify_sic(6798,"Real Estate Investment Trusts")["normalized_industry"]=="REIT"


def test_no_sic_is_unmapped_not_guessed():
    r=classify_sic(None,None)
    assert r["mapping_status"]=="NO_SIC" and r["normalized_industry"] is None


def test_manual_override_keeps_sic():
    r=industry_from_submissions("1",{"sic":"6021","sicDescription":"Bank"},
                                manual_sector="Financials",manual_reason="user")
    assert r["sector_source"]=="MANUAL_OVERRIDE"
    assert r["sic_original"]==6021 and r["normalized_industry"]=="Financials"
