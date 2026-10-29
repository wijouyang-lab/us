# -*- coding: utf-8 -*-
"""Tests for OHLC anomaly state transitions."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import ohlc_anomaly_registry as r  # noqa: E402


def test_default_open_cannot_close():
    a = {"date": "2008-03-19", "status": "OPEN", "evidence": []}
    assert r.can_close(a) is False


def test_verified_source_error_requires_evidence():
    a = {"date": "2008-03-19"}
    with pytest.raises(ValueError):
        r.transition(a, "VERIFIED_SOURCE_ERROR")
    out = r.transition(a, "VERIFIED_SOURCE_ERROR", evidence_urls=["https://example.test/source"])
    assert out["status"] == "VERIFIED_SOURCE_ERROR"


def test_resolution_requires_independent_source_and_evidence():
    a = {"date": "2008-03-19"}
    with pytest.raises(ValueError):
        r.transition(a, "RESOLVED_WITH_EVIDENCE", evidence_urls=["https://example.test/source"])
    out = r.transition(a, "RESOLVED_WITH_EVIDENCE",
                       evidence_urls=["https://example.test/independent"],
                       independent_source=True)
    assert r.can_close(out) is True
