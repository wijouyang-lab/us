# -*- coding: utf-8 -*-
"""Tests for the fail-closed candidate panel gate."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import candidate_panel_gate as g  # noqa: E402


def test_missing_license_rejected():
    out = g.evaluate({})
    assert out["approved"] is False
    assert "missing_code_license" in out["reasons"]
    assert "missing_data_license" in out["reasons"]


def test_restricted_upstream_rejected_even_with_labels():
    out = g.evaluate({"code_license": "MIT", "data_license": "MIT",
                      "contains_restricted_source": True,
                      "redistribution_allowed": True, "storage_allowed": True})
    assert out["approved"] is False
    assert "contains_restricted_upstream_data" in out["reasons"]


def test_complete_unrestricted_manifest_approved():
    out = g.evaluate({"code_license": "MIT", "data_license": "CC0",
                      "contains_restricted_source": False,
                      "redistribution_allowed": True, "storage_allowed": True})
    assert out["approved"] is True
