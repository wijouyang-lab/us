from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "dashboard-data.yml"


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
    assert re.search(
        r"(?m)^\s{4}if:\s*github\.ref\s*==\s*'refs/heads/main'\s*$",
        source,
    ), (
        "The Dashboard Data Refresh job needs a second main-ref guard so workflow_dispatch "
        "on a feature branch cannot run the main-writing job"
    )


def test_dashboard_writer_documents_fifteen_minute_cadence():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert re.search(r'(?m)^\s*- cron:\s*"\*/15 \* \* \* 1-5"\s*$', source)
    assert "工作日每 15 分钟刷新" in source


def test_dashboard_stop_comments_match_schedule_and_fresh_intraday_data():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "预期每 15 分钟检查" in source
    assert "时间戳新鲜的 5 分钟常规时段 bar" in source
    assert "任务延迟/数据过旧会 fail closed" in source
