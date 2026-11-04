# -*- coding: utf-8 -*-
import json
from pathlib import Path
import pytest
from tools.investment_research.dividend.dividend_event_parser_p44 import parse, is_false_positive
from tools.investment_research.dividend.dividend_event_verifier_p44 import verify, dedupe
from tools.investment_research.dividend.sec_filing_fetcher import FilingFetcher, archive_dir


def cat_text():
    return ("On June 10, 2026, the Board of Directors declared a quarterly dividend of $1.63 per share "
            "on common stock, an increase from $1.51 per share, payable August 19, 2026 to shareholders "
            "of record July 20, 2026.")


def bac_text():
    return ("On July 24, 2026, the Board declared a quarterly common stock dividend of $0.32 per share, "
            "payable September 25, 2026 to shareholders of record September 4, 2026. "
            "The Board also declared a dividend on preferred stock of $1.75 per share.")


def test_cat_new_dividend_not_previous():
    e = parse(cat_text(), ticker="CAT", cik="18230", source_url="https://www.sec.gov/x",
              accession="0001104659-26-072929", evidence_sha256="a"*64)[0]
    assert e["declared_per_share"] == 1.63
    assert e["previous_per_share"] == 1.51
    assert e["record_date"] == "2026-07-20" and e["payment_date"] == "2026-08-19"


def test_cat_announcement_and_filed_are_separate():
    e = parse(cat_text(), ticker="CAT", cik="18230", source_url="https://www.sec.gov/x",
              accession="A", evidence_sha256="a"*64, filed_date="2026-06-11")[0]
    assert e["announcement_date"] == "2026-06-10"
    assert e["filed_date"] == "2026-06-11"


def test_bac_common_032_not_preferred_175():
    e = parse(bac_text(), ticker="BAC", cik="70858", source_url="https://www.sec.gov/x",
              accession="B", evidence_sha256="b"*64)[0]
    assert e["declared_per_share"] == 0.32
    assert e["security_type"] == "COMMON"
    assert any(x.get("declared_per_share") != 1.75 for x in [e])


def test_preferred_only_text_no_common_event():
    assert parse("The Board declared a dividend on 7% preferred stock of $1.75 per share.",
                 ticker="BAC", cik="70858", source_url="https://www.sec.gov/x",
                 accession="B", evidence_sha256="b"*64) == []


def test_nee_price_target_is_false_positive():
    r = is_false_positive("Analysts set a price target of $67.75 for Dominion Energy shares.")
    assert r and r["reason"] == "FALSE_POSITIVE_NON_DIVIDEND_PRICE_TARGET"


def test_missing_ex_date_not_inferred():
    e = parse(cat_text(), ticker="CAT", cik="18230", source_url="https://www.sec.gov/x",
              accession="A", evidence_sha256="a"*64)[0]
    assert e["ex_date"] is None and e["ex_date_status"] == "EX_DATE_UNAVAILABLE"


def test_verified_requires_core_fields():
    e = parse(cat_text(), ticker="CAT", cik="18230", source_url="https://www.sec.gov/x",
              accession="A", evidence_sha256="a"*64)[0]
    v = verify([e], fetched_accessions={"A"})[0]
    assert v["verification_status"] == "VERIFIED"


def test_no_evidence_not_verified():
    e = {"ticker":"X","event_type":"DECLARED","security_type":"COMMON","declared_per_share":1.0,
         "announcement_date":"2026-01-01","source_url":"https://www.sec.gov/x","accession_number":"A",
         "evidence_sha256":""}
    assert verify([e])[0]["verification_status"] == "PARTIALLY_VERIFIED"


def test_same_event_dedupes():
    e = parse(cat_text(), ticker="CAT", cik="18230", source_url="https://www.sec.gov/x",
              accession="A", evidence_sha256="a"*64)[0]
    assert len(dedupe([e, e])) == 1


def test_archive_path():
    assert archive_dir("0000018230", "0001104659-26-072929").endswith("/18230/000110465926072929")


def test_full_scan_not_claimed():
    d = json.loads(Path("data/research/dividend_coverage_p44.json").read_text())
    assert d["summary"]["full_scan_completed"] is False
    assert d["summary"]["excluded_by_limit"] == 471


def test_581_is_not_downloaded_count():
    d = json.loads(Path("data/research/dividend_coverage_p44.json").read_text())
    assert d["summary"]["filings_seen_p43"] == 581
    assert d["summary"]["primary_downloaded_p43"] == 110


def test_no_real_ua_blocks_collection(monkeypatch, tmp_path):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    monkeypatch.delenv("ALLOW_SEC_PLACEHOLDER", raising=False)
    with pytest.raises(RuntimeError):
        FilingFetcher(tmp_path)


def test_false_positive_registry_present():
    d = json.loads(Path("data/research/dividend_false_positives_p44.json").read_text())
    assert d[0]["ticker"] == "NEE" and d[0]["is_event"] is False


def test_exhibit_99_1_is_actually_downloaded(tmp_path, monkeypatch):
    import hashlib, json
    class Fake(FilingFetcher):
        def _get(self, url, dest):
            dest.parent.mkdir(parents=True, exist_ok=True)
            if url.endswith("index.json"):
                dest.write_text(json.dumps({"directory": {"item": [
                    {"name": "cat-8k.htm", "type": "8-K", "description": "8-K"},
                    {"name": "cat_ex99-1.htm", "type": "EX-99.1", "description": "Press Release"}]}}))
            else:
                dest.write_text("<html>common stock dividend $1.63 per share</html>")
            raw = dest.read_bytes()
            return {"status": 200, "cached": False, "sha256": hashlib.sha256(raw).hexdigest(),
                    "bytes": len(raw), "path": str(dest), "url": url}
    f = Fake(tmp_path, "audit@example.org")
    out = f.fetch_filing("CAT", "18230", "0001104659-26-072929")
    assert out["status_text"] == "FETCHED_COMPLETE"
    assert any(x["name"] == "cat_ex99-1.htm" for x in out["exhibits"])
    assert out["primary"]["name"] == "cat-8k.htm"
