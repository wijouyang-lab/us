#!/usr/bin/env python3
"""Audit the machine-readable research status and its report."""
from __future__ import annotations

import json
from pathlib import Path

REQUIRED = {"phase", "research_area", "evidence_level", "data_status", "pit_status",
            "statistical_status", "portfolio_status", "deployment_status",
            "blocking_reasons", "source_pr", "last_verified_commit"}
LEVELS = set(range(0, 6))


def audit(status: dict, report_text: str = "") -> dict:
    errors = []
    phases = status.get("phases", [])
    if not isinstance(phases, list) or not phases:
        errors.append("no_phases")
    if status.get("deployment_eligible") is not False:
        errors.append("deployment_must_be_false")
    if status.get("pit_validated_count") != 0:
        errors.append("pit_count_must_be_zero")
    for p in phases:
        missing = REQUIRED - set(p)
        if missing:
            errors.append(f"{p.get('phase')}:missing_fields:{sorted(missing)}")
        if p.get("evidence_level") not in LEVELS:
            errors.append(f"{p.get('phase')}:bad_level")
        if p.get("pit_status") == "verified" and p.get("evidence_level", 0) < 4:
            errors.append(f"{p.get('phase')}:pit_without_level4")
        if p.get("portfolio_status") == "validated_non_overlapping" and p.get("evidence_level", 0) < 3:
            errors.append(f"{p.get('phase')}:portfolio_without_level3")
        if p.get("deployment_status") == "eligible":
            errors.append(f"{p.get('phase')}:deployment_eligible")
        if p.get("data_status") == "unavailable" and p.get("pit_status") == "verified":
            errors.append(f"{p.get('phase')}:pit_on_unavailable")
        if report_text and str(p.get("phase")) not in report_text:
            errors.append(f"{p.get('phase')}:missing_from_report")
    return {"ok": not errors, "errors": errors, "phases": len(phases),
            "current_results": sum(1 for p in phases if p.get("current_result") is True),
            "pit_validated": sum(1 for p in phases if p.get("pit_status") == "verified"),
            "portfolio_validated": sum(1 for p in phases if p.get("portfolio_status") == "validated_non_overlapping")}


def main():
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--status", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    status = json.loads(Path(a.status).read_text(encoding="utf-8"))
    report = Path(a.report).read_text(encoding="utf-8")
    out = audit(status, report)
    Path(a.output).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
