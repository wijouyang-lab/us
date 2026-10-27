from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "dashboard-data.yml"
PAPER_WORKFLOW = REPO / ".github" / "workflows" / "paper-trading.yml"


def test_dashboard_writer_is_restricted_to_main_pushes():
    source = WORKFLOW.read_text(encoding="utf-8")
    push = re.search(
        r"(?ms)^  push:\s*\n(?P<body>(?:^[ ]{4,}.*\n)+)",
        source,
    )
    assert push is not None, "Dashboard Data Refresh must retain an explicit push trigger"
    assert re.search(r"(?m)^    branches:\s*\[main\]\s*$", push.group("body")), (
        "The writer workflow must not run on feature-branch pushes because it can push HEAD to main"
    )


def test_dashboard_writer_job_has_main_ref_guard():
    source = WORKFLOW.read_text(encoding="utf-8")
    job = re.search(
        r"(?ms)^  refresh:\n(?P<body>(?:^[ ]{4,}.*\n)+)",
        source,
    )
    assert job is not None, "Dashboard Data Refresh refresh job must exist"
    assert re.search(r"github\.ref\s*==\s*'refs/heads/main'", job.group("body")), (
        "The Dashboard Data Refresh job must retain a main-ref guard, including when "
        "the guard is combined with workflow_run success checks"
    )


def test_dashboard_writer_documents_fifteen_minute_cadence():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert re.search(r'(?m)^\s*- cron:\s*"\*/15 13-21 \* \* \* 1-5"\s*$', source)
    assert "工作日每 15 分钟刷新" in source


def test_dashboard_stop_comments_match_schedule_and_fresh_intraday_data():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "预期每 15 分钟检查" in source
    assert "时间戳新鲜的 5 分钟常规时段 bar" in source
    assert "任务延迟/数据过旧会 fail closed" in source
 

def test_paper_trading_writer_is_main_only_and_scan_success_is_main_only():
    source = PAPER_WORKFLOW.read_text(encoding="utf-8")
    job = re.search(
        r"(?ms)^  paper:\n(?P<body>(?:^[ ]{4,}.*\n)+)",
        source,
    )
    assert job is not None, "Paper Trading writer job must exist"
    body = job.group("body")
    assert "github.ref == 'refs/heads/main'" in body, (
        "Paper Trading pushes its ledger to main and must never run from a feature ref"
    )
    assert "github.event.workflow_run.conclusion == 'success'" in body, (
        "Paper Trading may observe Scan only after successful completion"
    )
    assert "github.event.workflow_run.head_branch == 'main'" in body, (
        "A successful feature-branch Scan must not trigger a main-ledger write"
    )
