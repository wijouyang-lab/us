# -*- coding: utf-8 -*-
"""Regression tests for the low-frequency project's workflow trigger contract."""

from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO / ".github" / "workflows"


def _workflow(name):
    text = (WORKFLOWS / name).read_text(encoding="utf-8")
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line == "on:")
    end = next(
        (i for i in range(start + 1, len(lines))
         if lines[i] and not lines[i][0].isspace() and not lines[i].lstrip().startswith("#")),
        len(lines),
    )
    trigger = "\n".join(lines[start + 1:end])
    events = re.findall(r"(?m)^  ([A-Za-z_]+):\s*$", trigger)
    crons = re.findall(r"(?m)^\s+- cron:\s*['\"]?([^'\"\n]+)['\"]?\s*$", trigger)
    return text, trigger, set(events), crons


def test_scan_remains_external_dispatch_only():
    workflow, _trigger, events, crons = _workflow("scan.yml")

    assert events == {"workflow_dispatch"}
    assert crons == []
    assert "run: python scan.py" in workflow
    assert re.search(r"(?m)^  group: us-stock-scan$", workflow)
    assert re.search(r"(?m)^  cancel-in-progress: false$", workflow)


def test_review_keeps_only_dispatch_and_existing_weekday_schedule():
    workflow, _trigger, events, crons = _workflow("review.yml")

    assert events == {"workflow_dispatch", "schedule"}
    assert crons == ["23 22 * * 1-5"]
    assert re.search(r"(?m)^  group: us-stock-portfolio-ledger$", workflow)
    assert re.search(r"(?m)^  cancel-in-progress: false$", workflow)


def test_dashboard_refresh_schedule_and_push_scope_remain_narrow():
    workflow, trigger, events, crons = _workflow("dashboard-data.yml")

    assert events == {"schedule", "workflow_dispatch", "push", "workflow_run"}
    assert crons == ["*/15 13-21 * * 1-5"]
    assert re.search(r"(?m)^    branches: \[main\]$", trigger)
    for path in (
        "dashboard_export.py",
        "dashboard/fetch_runtimes.py",
        "dashboard/summarize_run.py",
        ".github/workflows/dashboard-data.yml",
    ):
        assert f"- {path}" in trigger
    assert re.search(r"(?m)^  group: us-stock-portfolio-ledger$", workflow)
    assert re.search(r"(?m)^  cancel-in-progress: false$", workflow)
    assert 'workflows: ["美股盘中扫描"]' in trigger
    assert "types: [completed]" in trigger
    assert "branches: [main]" in trigger
    assert "github.event.workflow_run.conclusion == 'success'" in workflow
    assert "github.event.workflow_run.head_branch == 'main'" in workflow


def test_quant_research_does_not_gain_an_independent_schedule():
    _workflow_text, _trigger, events, crons = _workflow("quant-research.yml")

    assert events == {"workflow_dispatch", "workflow_call"}
    assert crons == []


def test_price_history_rebuild_is_manual_and_fails_closed():
    workflow = (WORKFLOWS / "rebuild-quant-price-history.yml").read_text(encoding="utf-8")
    _text, _trigger, events, crons = _workflow("rebuild-quant-price-history.yml")
    assert events == {"workflow_dispatch"}
    assert crons == []
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "Invalid non-positive/non-finite" in workflow
    assert "expected_tickers - actual_tickers" in workflow
    assert "Backup SHA256" in workflow
    assert ".quant_price_history_rebuild_baseline.json" in workflow


def test_evolve_schedule_stays_monthly_and_manual():
    _workflow_text, _trigger, events, crons = _workflow("evolve.yml")

    assert events == {"workflow_dispatch", "schedule"}
    assert crons == ["0 2 1 * *"]
