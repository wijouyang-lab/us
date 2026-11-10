#!/usr/bin/env python3
"""Fail-closed gate for third-party research panels.

A code licence or a public repository does not grant rights to the underlying
price data. A panel is approved only when both code and data rights are recorded.
"""
from __future__ import annotations

from typing import Any


def evaluate(manifest: dict[str, Any]) -> dict[str, Any]:
    reasons = []
    if not manifest.get("code_license"):
        reasons.append("missing_code_license")
    if not manifest.get("data_license"):
        reasons.append("missing_data_license")
    if manifest.get("contains_restricted_source"):
        reasons.append("contains_restricted_upstream_data")
    if not manifest.get("redistribution_allowed"):
        reasons.append("redistribution_not_established")
    if not manifest.get("storage_allowed"):
        reasons.append("storage_not_established")
    return {"approved": not reasons, "reasons": reasons}
