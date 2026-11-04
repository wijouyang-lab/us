# -*- coding: utf-8 -*-
import json
from pathlib import Path
import pytest
from tools.investment_research.dividend.sec_fetch_manifest import (
    load, set_expected, upsert, complete, should_attempt, mark_text_scanned)
from tools.investment_research.dividend import dividend_full_scan_p45 as scan
from tools.investment_research.sec.rate_limiter import RateLimiter
from tools.investment_research.sec.client import SECClient


def accessions(n=2):
    return [{"ticker":"T","accession":f"A{i}"} for i in range(n)]


def good(acc):
    return {"status_text":"FETCHED_COMPLETE","index_url":"u","downloaded":1,"failed":0,
            "documents":[{"status":200,"sha256":"a"*64,"path":"x"}],
            "primary":{"status":200,"sha256":"a"*64}, "exhibits":[]}


def test_expected_inventory_is_required(tmp_path):
    m=load(tmp_path/"m.json"); assert not complete(m)
    set_expected(m, accessions(1)); assert not complete(m)


def test_partial_is_not_complete_and_is_retried(tmp_path):
    m=load(tmp_path/"m.json"); set_expected(m, accessions(1))
    upsert(m,"T","A0",{"status_text":"FETCHED_PARTIAL","index_url":"u","downloaded":1,"failed":1,
                       "documents":[{"status":200,"sha256":"a"},{"status":500}],
                       "primary":{"status":200,"sha256":"a"},"exhibits":[{"status":500}]})
    assert not complete(m); assert should_attempt(m,"A0")


def test_all_complete_requires_text_scan(tmp_path):
    m=load(tmp_path/"m.json"); set_expected(m, accessions(1))
    upsert(m,"T","A0",good("A0"))
    assert not complete(m)
    mark_text_scanned(m,"A0")
    assert complete(m)


def test_missing_accession_blocks_complete(tmp_path):
    m=load(tmp_path/"m.json"); set_expected(m, accessions(2))
    upsert(m,"T","A0",good("A0")); mark_text_scanned(m,"A0")
    assert not complete(m)


def test_config_blocked_no_network(monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT",raising=False)
    r=scan.run(); assert r["status"]=="CONFIGURATION_BLOCKED"


def test_gitignore_covers_p45():
    s=Path(".gitignore").read_text()
    assert "data/sec/filings_p45/" in s


def test_rate_limiter_global_interval(monkeypatch):
    times=[]
    def clock(): return times[-1] if times else 0.0
    def sleep(x): times.append(times[-1]+x if times else x)
    lim=RateLimiter(0.25, clock=clock, sleep=sleep)
    import tools.investment_research.sec.client as c
    monkeypatch.setattr(c,"get_rate_limiter",lambda: lim)
    a=SECClient(Path("cache1"),"audit@example.org"); b=SECClient(Path("cache2"),"audit@example.org")
    a._wait(); b._wait()
    assert times[-1] >= 0.25


def test_placeholder_invalid(monkeypatch):
    from tools.investment_research.dividend.sec_filing_fetcher import config_status
    monkeypatch.setenv("SEC_USER_AGENT","research contact@example.com")
    assert config_status()=="SEC_USER_AGENT_INVALID"


def test_failed_exhibit_is_partial():
    a={"status":"FETCHED_PARTIAL","text_scanned":True,"documents":[{"status":200,"sha256":"x"},{"status":500}]}
    assert not complete({"expected_accessions":["A"],"accessions":{"A":a}})


def test_repeated_upsert_does_not_duplicate():
    m={"expected_accessions":["A"],"accessions":{}}
    upsert(m,"T","A",good("A")); upsert(m,"T","A",good("A"))
    assert list(m["accessions"])==["A"]
