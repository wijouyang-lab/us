import json
from pathlib import Path
from unittest import mock

import pytest

from tools.automation.artifact import build_artifact, read_manifest
from tools.automation.redact import MAX_SUMMARY, redact
from tools.automation.validate import validate_base

ROOT = Path(__file__).resolve().parents[1]


def test_redact_removes_credentials_and_limits_length():
    text = "DEEPSEEK_API_KEY=sk-test-not-real\nGH_TOKEN=gh-test-not-real\nNORMAL=visible\n" + "x" * 5000
    out = redact(text)
    assert "sk-test-not-real" not in out
    assert "gh-test-not-real" not in out
    assert "NORMAL=visible" in out
    assert len(out) <= MAX_SUMMARY + 20
    assert "<truncated>" in out


def test_artifact_has_no_raw_prompt_or_output(tmp_path):
    repo = tmp_path / "repo"
    (repo / "docs/research").mkdir(parents=True)
    (repo / "docs/research/a.md").write_text("a", encoding="utf-8")
    out = tmp_path / "art"
    manifest = {"task_id": "t", "branch": "fix/t", "base_branch": "main", "source_commit_sha": "a" * 40, "base_commit_sha": "b" * 40, "status": "AGENT_COMPLETE", "timed_out": False, "tests_returncode": 0, "diagnostic_summary": "safe summary"}
    build_artifact(repo, out, manifest, ["docs/research/a.md"])
    data = (out / "manifest.json").read_text(encoding="utf-8")
    assert "prompt" not in data
    assert "final" not in data
    assert "sk-test" not in data
    read_manifest(out)


def test_workflow_has_no_raw_log_upload_and_dry_gate():
    text = (ROOT / ".github/workflows/dsh-task.yml").read_text(encoding="utf-8")
    assert "Upload DSH log" not in text
    assert "dsh-log-" not in text
    assert "DRY_RUN_VALIDATION_ONLY" in text
    assert 'if: inputs.dry_run == false' in text
    assert "dsh-task-${{ inputs.branch }}" in text
    assert "queue: max" in text


def test_base_branch_only_main():
    assert validate_base("main") == "main"
    with pytest.raises(ValueError):
        validate_base("release")


def test_preflight_fails_closed_on_api_errors(monkeypatch):
    import tools.automation.preflight as p
    calls = []

    class R:
        returncode = 1
        stdout = ""

    def fake(args, **kwargs):
        calls.append(args)
        if args[:2] == ["gh", "repo"]:
            return type("X", (), {"returncode": 0, "stdout": "o/r\n"})()
        return R()

    monkeypatch.setattr(p.subprocess, "run", fake)
    monkeypatch.setattr("sys.argv", ["preflight", "--task-id", "t", "--branch", "fix/t", "--base-branch", "main"])
    assert p.main() == 1
    assert calls


def test_preflight_protected_without_rules_blocks(monkeypatch):
    import tools.automation.preflight as p

    class R:
        def __init__(self, rc, out):
            self.returncode = rc
            self.stdout = out

    def fake(args, **kwargs):
        if args[:2] == ["gh", "repo"]:
            return R(0, "o/r\n")
        if args[-1].endswith("/branches/main"):
            return R(0, json.dumps({"protected": True}))
        return R(404, "")

    monkeypatch.setattr(p.subprocess, "run", fake)
    monkeypatch.setattr("sys.argv", ["preflight", "--task-id", "t", "--branch", "fix/t", "--base-branch", "main"])
    assert p.main() == 1


def test_lock_gate_and_action_pinning():
    wf = (ROOT / ".github/workflows/dsh-task.yml").read_text(encoding="utf-8")
    assert 'DSH_REQUIRE_LOCK: "1"' in wf
    assert "DSH_WORKFLOW_CONTEXT: publisher" in wf
    assert "BLOCKED:LOCK_NOT_IMPLEMENTED" in (ROOT / "tools/automation/publisher.py").read_text(encoding="utf-8")
    for path in (".github/workflows/dsh-task.yml", ".github/workflows/test.yml"):
        for line in (ROOT / path).read_text(encoding="utf-8").splitlines():
            if "uses:" in line:
                assert "@" in line and len(line.split("@", 1)[1].split()[0]) == 40


def test_locked_dsh_runtime_assets_exist():
    import json
    pkg = json.loads((ROOT / "dsh-runtime/package.json").read_text(encoding="utf-8-sig"))
    assert pkg["dependencies"]["@deepseek-ai/dsh"] == "0.2.0-rc.2"
    lock = json.loads((ROOT / "dsh-runtime/package-lock.json").read_text(encoding="utf-8-sig"))
    assert lock["packages"]["node_modules/@deepseek-ai/dsh"]["version"] == "0.2.0-rc.2"
    assert (ROOT / "tools/automation/dsh_subprocess_probe.mjs").exists()

def test_workflow_context_required(monkeypatch):
    from tools.automation.publisher import workflow_context_ok
    for key in list(("GITHUB_REPOSITORY", "GITHUB_WORKFLOW", "GITHUB_JOB", "GITHUB_RUN_ID", "DSH_WORKFLOW_CONTEXT")):
        monkeypatch.delenv(key, raising=False)
    assert workflow_context_ok() is False
    monkeypatch.setenv("GITHUB_REPOSITORY", "wijouyang-lab/us")
    monkeypatch.setenv("GITHUB_WORKFLOW", "Wrong")
    assert workflow_context_ok() is False

def test_oidc_signature_and_claim_rejection():
    import json, os, subprocess
    from tools.automation.oidc import verify_token
    out = json.loads(subprocess.check_output(["node", "tools/automation/oidc_test_token.mjs"], text=True))
    assert verify_token(out["token"], out["jwks"])["ok"] is True
    assert verify_token(out["token"][:-4] + "AAAA", out["jwks"])["ok"] is False
    assert verify_token("x.y.z", out["jwks"])["ok"] is False


def test_publisher_blocks_without_oidc(monkeypatch, tmp_path):
    from tools.automation.publisher import workflow_context_ok
    monkeypatch.delenv("DSH_OIDC_TOKEN", raising=False)
    monkeypatch.delenv("DSH_OIDC_JWKS_FILE", raising=False)
    assert workflow_context_ok() is False
