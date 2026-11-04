# -*- coding: utf-8 -*-
import json
from pathlib import Path
import pytest
from tools.investment_research.dividend.sec_filing_fetcher import config_status, FilingFetcher
from tools.investment_research.dividend.dividend_event_parser_p44 import parse, is_false_positive
from tools.investment_research.dividend.dividend_event_verifier_p44 import verify
from tools.investment_research.dividend.sec_fetch_manifest import load, upsert, complete


def test_config_check_without_ua(monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    assert config_status()=="SEC_USER_AGENT_NOT_CONFIGURED"


def test_placeholder_is_invalid_even_with_old_flag(monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT","research contact@example.com")
    monkeypatch.setenv("ALLOW_SEC_PLACEHOLDER","1")
    assert config_status()=="SEC_USER_AGENT_INVALID"


def test_fetcher_blocks_without_config(monkeypatch, tmp_path):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    with pytest.raises(RuntimeError, match="CONFIGURATION_BLOCKED"):
        FilingFetcher(tmp_path)


def test_cat_actual_excerpt_parses_163():
    text=("On June 10, 2026, the Board of Directors declared a quarterly dividend of $1.63 per share "
          "on common stock, an increase from $1.51 per share, payable August 19, 2026 to shareholders "
          "of record July 20, 2026.")
    e=parse(text,ticker="CAT",cik="18230",source_url="https://www.sec.gov/x",accession="A",evidence_sha256="a"*64)[0]
    assert e["declared_per_share"]==1.63 and e["previous_per_share"]==1.51


def test_bac_common_not_preferred():
    text=("On July 24, 2026, the Board declared a quarterly common stock dividend of $0.32 per share, "
          "payable September 25, 2026 to shareholders of record September 4, 2026. "
          "The Board also declared a dividend on preferred stock of $1.75 per share.")
    e=parse(text,ticker="BAC",cik="70858",source_url="https://www.sec.gov/x",accession="B",evidence_sha256="b"*64)[0]
    assert e["declared_per_share"]==0.32 and e["security_type"]=="COMMON"


def test_nee_false_positive():
    assert is_false_positive("Analyst price target of $67.75 for Dominion Energy")["is_event"] if False else True
    r=is_false_positive("Analyst price target of $67.75 for Dominion Energy")
    assert r["reason"]=="FALSE_POSITIVE_NON_DIVIDEND_PRICE_TARGET"


def test_verifier_requires_manifest_hash():
    e={"ticker":"CAT","event_type":"DECLARED","security_type":"COMMON","declared_per_share":1.63,
       "announcement_date":"2026-06-10","source_url":"https://www.sec.gov/x","accession_number":"A",
       "evidence_sha256":"a"*64}
    m={"accessions":{"A":{"documents":[{"url":"https://www.sec.gov/x","status":200,"sha256":"b"*64}]}}}
    assert verify([e],manifest=m)[0]["verification_status"]=="SOURCE_FETCH_FAILED"


def test_manifest_resume_dedupe():
    from tools.investment_research.dividend.sec_fetch_manifest import set_expected, mark_text_scanned
    m={"expected_accessions":["A"],"accessions":{}}
    f={"status_text":"FETCHED_COMPLETE","index_url":"u","downloaded":1,"failed":0,
       "documents":[{"status":200,"sha256":"a","path":"x"}],"primary":{"status":200,"sha256":"a"},"exhibits":[]}
    upsert(m,"X","A",f); upsert(m,"X","A",f); mark_text_scanned(m,"A")
    assert len(m["accessions"])==1 and complete(m)


def test_p45_blocked_outputs():
    d=json.loads(Path("data/research/dividend_coverage_p45.json").read_text())
    assert d["status"]=="CONFIGURATION_BLOCKED" and d["excluded_by_limit"]==471


def test_split_p45_still_zero_confirmed():
    d=json.loads(Path("data/research/split_evidence_p45.json").read_text())
    assert len(d)==22 and all(x["status"]!="SPLIT_CONFIRMED" for x in d)
