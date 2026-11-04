# -*- coding: utf-8 -*-
import json, hashlib, subprocess
from pathlib import Path
from tools.investment_research.dividend.dividend_cache_audit_p47 import audit, CACHE

D = json.loads(Path("data/research/dividend_cache_audit_p47.json").read_text())


def test_cache_inventory_actual():
    assert D["accession_count"] == 131
    assert sum(len(x["documents"]) for x in D["accessions"]) == 221
    assert D["status_counts"] == {"EXHIBIT_REQUIRED": 81, "PRIMARY_CACHED": 47, "EXHIBIT_CACHED": 3}


def test_all_hashes_present_and_reproducible():
    row = next(x for x in D["accessions"] if x["documents"])
    doc = row["documents"][0]
    assert doc["sha256"] and len(doc["sha256"]) == 64
    raw = (CACHE / row["accession"] / doc["name"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == doc["sha256"]


def test_mapping_success_and_unmapped():
    assert sum(1 for x in D["accessions"] if x["ticker"]) == 122
    assert any(not x["ticker"] for x in D["accessions"])


def test_cat_and_bac_require_exhibit():
    cat = next(x for x in D["accessions"] if x["accession"] == "000110465926072929")
    bac = next(x for x in D["accessions"] if x["accession"] == "000007085826000364")
    assert cat["status"] == "EXHIBIT_REQUIRED" and not cat["exhibits"]
    assert bac["status"] == "EXHIBIT_REQUIRED"


def test_nee_false_positive_cached():
    c = next(x for x in D["candidates"] if x.get("accession") == "000110465926100476")
    assert c["candidate_type"] == "FALSE_POSITIVE" and c["is_event"] is False


def test_all_candidates_preliminary():
    for c in D["candidates"]:
        assert c["evidence_status"] == "PRELIMINARY_LEGACY_CACHE"
        assert c["verification_status"] == "PRELIMINARY_ONLY"
        assert c["is_event"] is False


def test_legacy_provenance_global():
    assert D["provenance_status"] == "LEGACY_PLACEHOLDER_UA"
    assert D["evidence_status"] == "PRELIMINARY_ONLY"


def test_no_verification_or_split_confirmed_claim():
    text = Path("data/research/dividend_cache_audit_p47.json").read_text()
    assert '"verification_status": "VERIFIED"' not in text
    assert '"SPLIT_CONFIRMED"' not in text
    assert len(D["split_mentions"]) == 21


def test_cache_is_gitignored():
    r = subprocess.run(["git", "check-ignore", "data/sec/filings_p43/000110465926072929"],
                       capture_output=True, text=True)
    assert r.returncode == 0


def test_no_network_imports_in_audit():
    src = Path("tools/investment_research/dividend/dividend_cache_audit_p47.py").read_text()
    assert "urllib" not in src and "requests" not in src and "httpx" not in src


def test_candidate_missing_dates_not_inferred():
    for c in D["candidates"]:
        assert c.get("ex_date") is None
        assert c.get("ex_date_status") in (None, "EX_DATE_UNAVAILABLE")


def test_audit_rerun_is_deterministic():
    a = audit()
    assert a["accession_count"] == D["accession_count"]
    assert a["status_counts"] == D["status_counts"]
