# -*- coding: utf-8 -*-
"""Regression tests for the low-frequency project's workflow trigger contract."""

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO / ".github" / "workflows"


def _workflow(name):
    data = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    # PyYAML's YAML 1.1 resolver may parse the unquoted key "on" as True.
    events = data.get(True, data.get("on"))
    assert isinstance(events, dict), name
    return data, events


def test_scan_remains_external_dispatch_only():
    workflow, events = _workflow("scan.yml")

    assert set(events) == {"workflow_dispatch"}
    assert "schedule" not in events
    assert "push" not in events
    assert "pull_request" not in events

    assert workflow["concurrency"]["group"] == "us-stock-scan"
    assert workflow["concurrency"]["cancel-in-progress"] is False
    assert any(
        step.get("run") == "python scan.py"
        for step in workflow["jobs"]["scan"]["steps"]
    )


def test_review_keeps_only_dispatch_and_existing_weekday_schedule():
    workflow, events = _workflow("review.yml")

    assert set(events) == {"workflow_dispatch", "schedule"}
    assert [x["cron"] for x in events["schedule"]] == ["23 22 * * 1-5"]
    assert workflow["concurrency"]["group"] == "us-stock-portfolio-ledger"
    assert workflow["concurrency"]["cancel-in-progress"] is False


def test_dashboard_refresh_schedule_and_push_scope_remain_narrow():
    workflow, events = _workflow("dashboard-data.yml")

    assert set(events) == {"schedule", "workflow_dispatch", "push"}
    assert [x["cron"] for x in events["schedule"]] == ["0 * * * 1-5"]
    assert events["push"]["branches"] == ["main"]
    assert events["push"]["paths"] == [
        "dashboard_export.py",
        "dashboard/fetch_runtimes.py",
        "dashboard/summarize_run.py",
        ".github/workflows/dashboard-data.yml",
    ]
    assert workflow["concurrency"]["group"] == "us-stock-portfolio-ledger"
    assert workflow["concurrency"]["cancel-in-progress"] is False


def test_quant_research_does_not_gain_an_independent_schedule():
    _, events = _workflow("quant-research.yml")

    assert set(events) == {"workflow_dispatch", "workflow_call"}
    assert "schedule" not in events
    assert "push" not in events


def test_evolve_schedule_stays_monthly_and_manual():
    _, events = _workflow("evolve.yml")

    assert set(events) == {"workflow_dispatch", "schedule"}
    assert [x["cron"] for x in events["schedule"]] == ["0 2 1 * *"]
