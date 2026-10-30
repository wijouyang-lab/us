# -*- coding: utf-8 -*-
"""Tests for research status audit."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
from research_status_audit import audit  # noqa: E402

ROOT = Path(__file__).resolve().parents[1] / "docs" / "research"


def status():
    return {
        "deployment_eligible": False, "pit_validated_count": 0,
        "phases": [{"phase": "2.1", "research_area": "x", "evidence_level": 1,
                    "data_status": "partial", "pit_status": "failed",
                    "statistical_status": "n/a", "portfolio_status": "not_tested",
                    "deployment_status": "not_eligible", "blocking_reasons": [],
                    "source_pr": 409, "last_verified_commit": "abc",
                    "current_result": True}],
    }


def test_valid_status_passes():
    out = audit(status(), "2.1")
    assert out["ok"] is True
    assert out["pit_validated"] == 0


def test_pit_claim_without_level4_fails():
    s = status()
    s["phases"][0]["pit_status"] = "verified"
    out = audit(s, "2.1")
    assert out["ok"] is False
    assert any("pit_without_level4" in e for e in out["errors"])


def test_deployment_claim_fails():
    s = status()
    s["deployment_eligible"] = True
    assert audit(s, "2.1")["ok"] is False


def test_missing_report_phase_fails():
    assert audit(status(), "other")["ok"] is False


def test_repository_status_is_valid():
    s = json.loads((ROOT.parents[1] / "data" / "research" / "research_status.json").read_text())
    report = (ROOT / "RESEARCH_STATUS_MASTER.md").read_text()
    assert audit(s, report)["ok"] is True
