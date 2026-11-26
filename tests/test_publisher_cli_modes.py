import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def setup(tmp_path):
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
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "gh.log"
    gh = bindir / "gh"
    gh.write_text("""#!/bin/sh
echo "$1 $2" >> "$GH_LOG"
if [ "$1 $2" = "pr list" ]; then
  case "$GH_MODE" in
    existing) echo '[{"url":"https://example/pr/1","isDraft":true,"headRefName":"fix/t","baseRefName":"main"}]' ;;
    ready) echo '[{"url":"https://example/pr/1","isDraft":false,"headRefName":"fix/t","baseRefName":"main"}]' ;;
    multiple) echo '[{"url":"https://example/pr/1","isDraft":true,"headRefName":"fix/t","baseRefName":"main"},{"url":"https://example/pr/2","isDraft":true,"headRefName":"fix/t","baseRefName":"main"}]' ;;
    queryfail) exit 7 ;;
    *) echo '[]' ;;
  esac
  exit 0
fi
if [ "$1 $2" = "pr create" ]; then
  if [ "$GH_MODE" = "createfail" ]; then exit 9; fi
  echo 'https://example/pr/1'; exit 0
fi
if [ "$1 $2" = "pr view" ]; then
  echo '{"url":"https://example/pr/1","isDraft":true,"headRefName":"fix/t","baseRefName":"main"}'; exit 0
fi
exit 1
""", encoding="utf-8")
    gh.chmod(0o755)
    return repo, art, bindir, log


def run_publisher(repo, art, bindir, log, mode):
    env = dict(os.environ, PATH=f"{bindir}:{os.environ.get('PATH','')}", PYTHONPATH=str(ROOT), GH_MODE=mode, GH_LOG=str(log))
    cmd = [sys.executable, "-c", "from tools.automation import publisher; raise SystemExit(publisher._publish_main())", "--repo", str(repo), "--artifact", str(art), "--state", "automation/state/tasks.json", "--task-id", "t", "--branch", "fix/t", "--base-branch", "main"]
    return subprocess.run(cmd, cwd=repo, env=env, text=True, capture_output=True)


@pytest.mark.skipif(os.name == "nt", reason="POSIX mock gh integration")
@pytest.mark.parametrize("mode,expected,status", [("existing", 0, "REVIEW_PENDING"), ("ready", 1, "BLOCKED"), ("multiple", 1, "BLOCKED"), ("queryfail", 1, "PUBLISHING"), ("createfail", 1, "PUBLISHING")])
def test_draft_pr_modes(tmp_path, mode, expected, status):
    repo, art, bindir, log = setup(tmp_path)
    r = run_publisher(repo, art, bindir, log, mode)
    assert r.returncode == expected, r.stdout + r.stderr
    state = json.loads((repo / "automation/state/tasks.json").read_text())
    assert state["tasks"]["t"]["status"] == status
    creates = [line for line in log.read_text().splitlines() if line == "pr create"]
    assert len(creates) == (1 if mode in {"createfail"} else 0)


@pytest.mark.skipif(os.name == "nt", reason="POSIX hook/mock gh integration")
def test_business_push_rejected_then_retry(tmp_path):
    repo, art, bindir, log = setup(tmp_path)
    bare = tmp_path / "remote.git"
    hook = bare / "hooks/pre-receive"
    hook.write_text("#!/bin/sh\nn=$(cat .push-count 2>/dev/null || echo 0)\nn=$((n+1))\necho $n > .push-count\nif [ $n -eq 1 ]; then exit 0; fi\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    r = run_publisher(repo, art, bindir, log, "no-pr")
    assert r.returncode == 1
    state = json.loads((repo / "automation/state/tasks.json").read_text())
    assert state["tasks"]["t"]["status"] == "PUBLISHING"
    assert state["tasks"]["t"]["last_review"]["reason"] == "BUSINESS_PUSH_FAILED"
    hook.unlink()
    r2 = run_publisher(repo, art, bindir, log, "no-pr")
    assert r2.returncode == 0, r2.stdout + r2.stderr
    subjects = subprocess.check_output(["git", "log", "origin/fix/t", "--format=%s"], cwd=repo, text=True).splitlines()
    assert len([s for s in subjects if s.startswith("automation: DSH task")]) == 1
    creates = [line for line in log.read_text().splitlines() if line == "pr create"]
    assert len(creates) == 1


@pytest.mark.skipif(os.name == "nt", reason="POSIX mock gh integration")
def test_pr_query_failure_retry(tmp_path):
    repo, art, bindir, log = setup(tmp_path)
    assert run_publisher(repo, art, bindir, log, "queryfail").returncode == 1
    assert json.loads((repo / "automation/state/tasks.json").read_text())["tasks"]["t"]["status"] == "PUBLISHING"
    assert run_publisher(repo, art, bindir, log, "no-pr").returncode == 0
    assert json.loads((repo / "automation/state/tasks.json").read_text())["tasks"]["t"]["status"] == "REVIEW_PENDING"
    assert len([x for x in log.read_text().splitlines() if x == "pr create"]) == 1


@pytest.mark.skipif(os.name == "nt", reason="POSIX mock gh integration")
def test_pr_create_failure_retry(tmp_path):
    repo, art, bindir, log = setup(tmp_path)
    assert run_publisher(repo, art, bindir, log, "createfail").returncode == 1
    assert json.loads((repo / "automation/state/tasks.json").read_text())["tasks"]["t"]["status"] == "PUBLISHING"
    assert run_publisher(repo, art, bindir, log, "no-pr").returncode == 0
    assert json.loads((repo / "automation/state/tasks.json").read_text())["tasks"]["t"]["status"] == "REVIEW_PENDING"


@pytest.mark.skipif(os.name == "nt", reason="POSIX fresh-clone integration")
def test_business_push_rejected_then_fresh_clone_retry(tmp_path):
    repo, art, bindir, log = setup(tmp_path)
    bare = tmp_path / "remote.git"
    hook = bare / "hooks/pre-receive"
    hook.write_text("#!/bin/sh\nn=$(cat .push-count 2>/dev/null || echo 0)\nn=$((n+1))\necho $n > .push-count\nif [ $n -eq 1 ]; then exit 0; fi\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    assert run_publisher(repo, art, bindir, log, "no-pr").returncode == 1
    hook.unlink()
    remote_head = subprocess.check_output(["git", "rev-parse", "fix/t"], cwd=bare, text=True).strip()
    fresh = tmp_path / "fresh"
    subprocess.run(["git", "clone", str(bare), str(fresh)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=fresh, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=fresh, check=True)
    subprocess.run(["git", "switch", "-c", "fix/t", "origin/fix/t"], cwd=fresh, check=True)
    initial = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fresh, text=True).strip()
    assert initial == remote_head
    r2 = run_publisher(fresh, art, bindir, log, "no-pr")
    assert r2.returncode == 0, r2.stdout + r2.stderr
    subjects = subprocess.check_output(["git", "log", "origin/fix/t", "--format=%s"], cwd=fresh, text=True).splitlines()
    assert len([x for x in subjects if x.startswith("automation: DSH task")]) == 1
    assert len([x for x in log.read_text().splitlines() if x == "pr create"]) == 1
    state = json.loads((fresh / "automation/state/tasks.json").read_text())
    assert state["tasks"]["t"]["status"] == "REVIEW_PENDING"


