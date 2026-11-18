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

def test_python_lock_is_fully_pinned():
    from pathlib import Path
    lines = [x for x in Path("requirements-production.lock").read_text(encoding="utf-8").splitlines() if x and not x.startswith("#")]
    assert lines
    assert all("==" in x for x in lines)
    assert any(x.startswith("pandas==") for x in lines)

def test_explicit_extra_cannot_inject_credentials(tmp_path, monkeypatch):
    from tools.automation.headless import child_env
    monkeypatch.setenv("NORMAL_TEST_VAR", "visible")
    env = child_env({"DEEPSEEK_API_KEY": "sk-extra", "GH_TOKEN": "gh-extra", "NORMAL_TEST_VAR": "visible"})
    assert "DEEPSEEK_API_KEY" not in env
    assert "GH_TOKEN" not in env
    assert env.get("NORMAL_TEST_VAR") == "visible"

def test_production_cli_blocks_fake_oidc_env(tmp_path):
    import os, subprocess, sys
    from pathlib import Path
    env = dict(os.environ, GITHUB_ACTIONS="true", GITHUB_REPOSITORY="wijouyang-lab/us", GITHUB_WORKFLOW="DSH Headless Task", GITHUB_JOB="publisher", GITHUB_EVENT_NAME="workflow_dispatch", GITHUB_REF="refs/heads/deploy/dsh-automation-p0", GITHUB_RUN_ID="123456", DSH_WORKFLOW_CONTEXT="publisher", DSH_OIDC_TOKEN="fake", DSH_OIDC_JWKS_FILE="/tmp/fake")
    r = subprocess.run([sys.executable, "-m", "tools.automation.publisher", "--repo", str(tmp_path), "--artifact", str(tmp_path), "--task-id", "t", "--branch", "fix/t", "--base-branch", "main"], env=env, text=True, capture_output=True)
    assert r.returncode != 0
    assert "BLOCKED:WORKFLOW_CONTEXT_UNVERIFIED" in r.stdout

def _oidc_case(claims=None, remove=None, kid=None, alg=None):
    import json, subprocess
    inp = {"claims": claims or {}, "remove": remove or []}
    if kid:
        inp["kid"] = kid
    if alg:
        inp["alg"] = alg
    out = json.loads(subprocess.check_output(["node", "tools/automation/oidc_test_token.mjs"], input=json.dumps(inp), text=True))
    return out


def test_oidc_full_negative_claim_matrix():
    from tools.automation.oidc import verify_token
    base = _oidc_case()
    assert verify_token(base["token"], base["jwks"], {"run_id": "123456"})["ok"] is True
    cases = [
        _oidc_case({"iss": "https://evil.example"}),
        _oidc_case({"aud": "wrong"}),
        _oidc_case({"repository": "evil/repo"}),
        _oidc_case({"repository_id": "1"}),
        _oidc_case({"workflow_ref": "evil/workflow"}),
        _oidc_case({"ref": "refs/heads/main"}),
        _oidc_case({"event_name": "push"}),
        _oidc_case(remove=["exp"]),
        _oidc_case({"exp": 1}),
        _oidc_case({"nbf": 9999999999}),
        _oidc_case({"iat": 9999999999}),
        _oidc_case({"run_id": "not-a-number"}),
        _oidc_case({"run_id": "999"}),
        _oidc_case(kid="missing-kid"),
        _oidc_case(alg="HS256"),
        _oidc_case(remove=["repository"]),
    ]
    for i, item in enumerate(cases):
        expected = {"run_id": "123456"}
        assert verify_token(item["token"], item["jwks"], expected)["ok"] is False, i
    tampered = base["token"][:-4] + "AAAA"
    assert verify_token(tampered, base["jwks"], {"run_id": "123456"})["ok"] is False

def test_test_harness_not_in_production_entrypoints():
    from pathlib import Path
    workflow = Path(".github/workflows/dsh-task.yml").read_text(encoding="utf-8")
    agent = Path("tools/automation/agent_task.py").read_text(encoding="utf-8")
    assert "publisher_cli" not in workflow
    assert "publisher_cli" not in agent
    assert "_TEST_HARNESS" not in (Path("tools/automation/agent_task.py").read_text(encoding="utf-8"))

def test_production_main_locks_after_valid_context(monkeypatch):
    from tools.automation import publisher
    monkeypatch.setattr(publisher, "workflow_context_ok", lambda: True)
    assert publisher.main() == 3
    source = (__import__("pathlib").Path("tools/automation/publisher.py")).read_text(encoding="utf-8")
    assert "_TEST_HARNESS" not in source
    assert "globals()" not in source

def test_oidc_request_url_origin_protection(monkeypatch):
    from tools.automation.oidc import _valid_oidc_request_url
    assert _valid_oidc_request_url("https://pipelines.actions.githubusercontent.com/x")
    assert not _valid_oidc_request_url("http://pipelines.actions.githubusercontent.com/x")
    assert not _valid_oidc_request_url("https://evil.example/x")
    assert not _valid_oidc_request_url("https://user:pass@pipelines.actions.githubusercontent.com/x")
    assert not _valid_oidc_request_url("https://pipelines.actions.githubusercontent.com:8443/x")

def test_oidc_http_missing_and_bad_endpoint(monkeypatch):
    from tools.automation import oidc
    monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_URL", raising=False)
    monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", raising=False)
    assert oidc._fetch_actions_token() == ""
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", "http://evil.example/token")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "test-bearer")
    assert oidc._fetch_actions_token() == ""
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", "https://pipelines.actions.githubusercontent.com/x?api-version=2")
    called = []
    class Boom:
        def open(self, *args, **kwargs):
            called.append(True)
            raise RuntimeError("redirect")
    import urllib.request
    monkeypatch.setattr(urllib.request, "build_opener", lambda *a, **k: Boom())
    try:
        oidc._fetch_actions_token()
    except RuntimeError:
        pass
    assert called

def test_real_model_gate_defaults_disabled():
    wf = (ROOT / ".github/workflows/dsh-task.yml").read_text(encoding="utf-8")
    assert "vars.DSH_REAL_MODEL_ENABLED == 'true'" in wf
    assert "BLOCKED:REAL_MODEL_EXECUTION_DISABLED" in wf
    agent = wf.split("  agent:", 1)[1].split("  publisher:", 1)[0]
    assert "DEEPSEEK_API_KEY" in agent
    preflight = wf.split("  preflight:", 1)[1].split("  dsh-install-verify:", 1)[0]
    assert "DEEPSEEK_API_KEY" not in preflight
    publisher = wf.split("  publisher:", 1)[1]
    assert "DEEPSEEK_API_KEY" not in publisher
