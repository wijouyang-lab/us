# -*- coding: utf-8 -*-
import pytest
from tools.investment_research.dividend.dividend_events import make_event, dedupe, annual_change_flags


def test_event_requires_source_and_hash():
    e=make_event(ticker="X",cik="1",event_type="DECLARED",event_date="2025-05-01",
                 source_url="https://example.com/ir",source_type="issuer",evidence=b"declared")
    assert e.event_id.startswith("DIV-") and e.status=="UNVERIFIED"


def test_event_rejects_unknown_type():
    with pytest.raises(ValueError):
        make_event(ticker="X",cik="1",event_type="GUESS",event_date="2025-05-01",
                   source_url="https://example.com",source_type="issuer",evidence="x")


def test_events_dedupe_by_evidence_id():
    a=make_event(ticker="X",cik="1",event_type="DECLARED",event_date="2025-05-01",
                 source_url="https://example.com",source_type="issuer",evidence="x")
    b=make_event(ticker="X",cik="1",event_type="DECLARED",event_date="2025-05-01",
                 source_url="https://example.com",source_type="issuer",evidence="x")
    assert len(dedupe([a,b]))==1


def test_annual_change_is_not_an_event():
    flags=annual_change_flags([{"end":"2024","value":2.0},{"end":"2025","value":1.0}])
    assert flags[0]["is_event"] is False and flags[0]["type"]=="POSSIBLE_REDUCTION"
