# -*- coding: utf-8 -*-
"""Workflow safety guards for the monthly Evolve job."""

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "evolve.yml"

ALLOWED_OUTPUTS = (
    "strategy_params.json",
    "strategy_evolution.json",
    "evolved_rules.json",
    "dashboard/data/model_usage.json",
)


def test_evolve_workflow_stages_only_explicit_outputs():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    executable = "\n".join(
        line for line in workflow.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )

    assert "git add -A" not in executable
    assert "git add ." not in executable
    for path in ALLOWED_OUTPUTS:
        assert path in executable

    # The allowlist must be enforced against the actual staged paths.
    assert 'git diff --cached --name-only' in workflow
    assert 'strategy_params.json|strategy_evolution.json|evolved_rules.json|dashboard/data/model_usage.json' in workflow


def test_evolve_workflow_uses_safe_retry_push_without_force():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "bash tools/ci/push_with_retry.sh 3 5" in workflow
    assert "git push" not in "\n".join(
        line for line in workflow.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    assert "--force" not in workflow
    assert "force-with-lease" not in workflow


def test_evolve_schedule_and_gate_are_unchanged():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "cron: '0 2 1 * *'" in workflow
    assert "run: python evolve.py" in workflow
    assert "steps.check-date.outputs.should_run == 'true'" in workflow
