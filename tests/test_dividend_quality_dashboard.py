# -*- coding: utf-8 -*-
import json, subprocess, sys
from pathlib import Path
from scripts.export_dividend_quality_dashboard import build, _load, SRC_EVENTS, SRC_AUDIT, SRC_EXCL

OUT = Path("dashboard/data/dividend_quality.json")


def test_cat_and_bac_values():
    d = json.loads(OUT.read_text())
    by = {e["ticker"]: e for e in d["events"]}
    assert by["CAT"]["declared_per_share"] == 1.63
    assert by["CAT"]["previous_per_share"] == 1.51
    assert by["CAT"]["increase_pct"] == 8
    assert by["BAC"]["declared_per_share"] == 0.32
    assert by["BAC"]["previous_per_share"] is None
    assert by["BAC"]["previous_per_share_status"] == "NOT_DISCLOSED_IN_FILING"
    assert by["BAC"]["increase_pct"] == 14


def test_bac_028_not_present():
    assert "$0.28" not in OUT.read_text()
    assert "0.28" not in OUT.read_text()


def test_preferred_exclusion():
    d = json.loads(OUT.read_text())
    ex = d["exclusions"]
    assert len(ex) == 1 and ex[0]["declared_per_share"] == 1.75
    assert ex[0]["status"] == "PREFERRED_STOCK_EXCLUDED_FROM_COMMON_DIVIDEND"


def test_ex_date_is_not_disclosed():
    for e in json.loads(OUT.read_text())["events"]:
        assert e["ex_date"] is None
        assert e["ex_date_status"] == "NOT_DISCLOSED_IN_FILING"


def test_only_verified_events_exported():
    d = build(_load(SRC_EVENTS), _load(SRC_AUDIT), _load(SRC_EXCL))
    assert len(d["events"]) == 2
    bad = _load(SRC_EVENTS); bad["events"][0]["verification_status"] = "PARTIALLY_VERIFIED"
    d2 = build(bad, _load(SRC_AUDIT), _load(SRC_EXCL))
    assert all(e["ticker"] != bad["events"][0]["ticker"] for e in d2["events"])


def test_sources_are_sec_https_and_hashes_match_audit():
    d = json.loads(OUT.read_text()); audit = _load(SRC_AUDIT)
    hashes = {h["sha256"] for h in audit["hashes"]}
    for e in d["events"]:
        assert len(e["sources"]) == 2
        for s in e["sources"]:
            assert s["url"].startswith("https://www.sec.gov/")
            assert s["sha256"] in hashes


def test_missing_research_keeps_snapshot(tmp_path):
    out = tmp_path / "dividend_quality.json"; out.write_text('{"keep":true}')
    r = subprocess.run([sys.executable, "scripts/export_dividend_quality_dashboard.py",
                        "--events", str(tmp_path/"missing-events.json"),
                        "--audit", str(tmp_path/"missing-audit.json"),
                        "--exclusions", str(tmp_path/"missing-exclusions.json"),
                        "--out", str(out)], capture_output=True, text=True)
    assert r.returncode == 0 and json.loads(out.read_text()) == {"keep": True}
    assert "keeping existing snapshot" in r.stdout


def test_sample_is_not_full_scan():
    m = json.loads(OUT.read_text())["metadata"]
    assert m["scope"] == "TARGETED_SAMPLE"
    assert m["full_scan_status"] == "NOT_RUN"
    assert m["verified_event_count"] == 2
    assert "并非完整覆盖" in m["coverage_note"]
    assert m["source_commit_sha"] == "6c131858bb2eef4ff9fd219caf3171813c217e6e"
