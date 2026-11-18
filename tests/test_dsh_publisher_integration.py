import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(os.name == "nt", reason="POSIX temp bare remote integration")
def test_publisher_temp_remote_and_idempotent_pr(tmp_path):
    from tools.automation.artifact import build_artifact

    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
    repo = tmp_path / "repo"
    subprocess.run(["git", "clone", str(bare), str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "docs/research").mkdir(parents=True)
    (repo / "docs/research/base.md").write_text("base", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo, check=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=repo, check=True)
    subprocess.run(["git", "switch", "-c", "fix/t"], cwd=repo, check=True)
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    (repo / "docs/research/new.md").write_text("new", encoding="utf-8")
    art = tmp_path / "agent-artifact"
    build_artifact(repo, art, {"task_id": "t", "branch": "fix/t", "base_branch": "main", "source_commit_sha": source, "base_commit_sha": source, "status": "AGENT_COMPLETE", "timed_out": False, "tests_returncode": 0}, ["docs/research/new.md"])
    bindir = tmp_path / "bin"; bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text("#!/bin/sh\nif [ \"$1 $2\" = \"pr list\" ]; then echo '[]'; exit 0; fi\nif [ \"$1 $2\" = \"pr create\" ]; then echo 'https://example/pr/1'; exit 0; fi\nif [ \"$1 $2\" = \"pr view\" ]; then echo '{\"url\":\"https://example/pr/1\",\"isDraft\":true,\"headRefName\":\"fix/t\",\"baseRefName\":\"main\"}'; exit 0; fi\nexit 1\n", encoding="utf-8")
    gh.chmod(0o755)
    env = dict(os.environ, PATH=f"{bindir}:{os.environ.get('PATH','')}", PYTHONPATH=str(ROOT))
    cmd = [sys.executable, "-c", "from tools.automation import publisher; raise SystemExit(publisher._publish_main())", "--repo", str(repo), "--artifact", str(art), "--state", "automation/state/tasks.json", "--task-id", "t", "--branch", "fix/t", "--base-branch", "main"]
    r = subprocess.run(cmd, cwd=repo, env=env, text=True, capture_output=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert subprocess.run(["git", "rev-parse", "origin/fix/t"], cwd=repo, text=True, capture_output=True).returncode == 0
    state = json.loads((repo / "automation/state/tasks.json").read_text())
    assert state["tasks"]["t"]["status"] == "REVIEW_PENDING"
    assert state["tasks"]["t"]["pr_url"] == "https://example/pr/1"
    before = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    r2 = subprocess.run(cmd, cwd=repo, env=env, text=True, capture_output=True)
    assert r2.returncode == 0
    after = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    assert before == after

