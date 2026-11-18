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
    bindir = tmp_path / "bin"; bindir.mkdir()
    log = tmp_path / "gh.log"
    gh = bindir / "gh"
    gh.write_text("""#!/bin/sh
echo "$1 $2" >> "$GH_LOG"
if [ "$1 $2" = "pr list" ]; then
  if [ "$GH_MODE" = "existing" ]; then echo '[{"url":"https://example/pr/1","isDraft":true,"headRefName":"fix/t","baseRefName":"main"}]'; else echo '[]'; fi
  exit 0
fi
if [ "$1 $2" = "pr create" ]; then echo 'https://example/pr/1'; exit 0; fi
if [ "$1 $2" = "pr view" ]; then echo '{"url":"https://example/pr/1","isDraft":true,"headRefName":"fix/t","baseRefName":"main"}'; exit 0; fi
exit 1
""", encoding="utf-8")
    gh.chmod(0o755)
    return repo, art, bindir, log


def run(repo, art, bindir, log, mode, extra_path=None):
    path = f"{bindir}:{os.environ.get('PATH','')}"
    if extra_path:
        path = f"{extra_path}:{path}"
    env = dict(os.environ, PATH=path, PYTHONPATH=str(ROOT), GH_MODE=mode, GH_LOG=str(log))
    cmd = [sys.executable, "-m", "tools.automation.publisher", "--repo", str(repo), "--artifact", str(art), "--state", "automation/state/tasks.json", "--task-id", "t", "--branch", "fix/t", "--base-branch", "main"]
    return subprocess.run(cmd, cwd=repo, env=env, text=True, capture_output=True)


def fresh(bare, tmp_path):
    dest = tmp_path / "fresh"
    subprocess.run(["git", "clone", str(bare), str(dest)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=dest, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=dest, check=True)
    if subprocess.run(["git", "rev-parse", "--verify", "origin/fix/t"], cwd=dest, capture_output=True).returncode == 0:
        subprocess.run(["git", "switch", "-c", "fix/t", "origin/fix/t"], cwd=dest, check=True)
    else:
        subprocess.run(["git", "switch", "-c", "fix/t", "origin/main"], cwd=dest, check=True)
    return dest


def push_wrapper(tmp_path, fail_at):
    bindir = tmp_path / "wrapper"; bindir.mkdir()
    state = tmp_path / "push-count"
    script = bindir / "git"
    script.write_text(f"""#!/bin/sh
for a in "$@"; do
  if [ "$a" = push ]; then
    n=$(cat "{state}" 2>/dev/null || echo 0); n=$((n+1)); echo $n > "{state}"
    /usr/bin/git "$@"; rc=$?
    if [ $n -eq {fail_at} ]; then exit 1; fi
    exit $rc
  fi
done
exec /usr/bin/git "$@"
""", encoding="utf-8")
    script.chmod(0o755)
    return bindir


@pytest.mark.skipif(os.name == "nt", reason="POSIX fresh-clone integration")
def test_publishing_state_push_accepted_client_error_fresh_clone(tmp_path):
    repo, art, bindir, log = setup(tmp_path)
    wrap = push_wrapper(tmp_path, 1)
    r = run(repo, art, bindir, log, "no-pr", wrap)
    assert r.returncode == 0, r.stdout + r.stderr
    bare = tmp_path / "remote.git"
    remote = subprocess.check_output(["git", "show", "fix/t:automation/state/tasks.json"], cwd=bare, text=True)
    assert '"status": "REVIEW_PENDING"' in remote
    f = fresh(bare, tmp_path)
    r2 = run(f, art, bindir, log, "existing")
    assert r2.returncode == 0
    assert len([x for x in log.read_text().splitlines() if x == "pr create"]) == 1


@pytest.mark.skipif(os.name == "nt", reason="POSIX fresh-clone integration")
def test_publishing_state_push_rejected_fresh_clone(tmp_path):
    repo, art, bindir, log = setup(tmp_path)
    hook = tmp_path / "remote.git/hooks/pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    assert run(repo, art, bindir, log, "no-pr").returncode == 1
    hook.unlink()
    remote = subprocess.run(["git", "show", "fix/t:automation/state/tasks.json"], cwd=tmp_path / "remote.git", capture_output=True)
    assert remote.returncode != 0
    f = fresh(tmp_path / "remote.git", tmp_path)
    r2 = run(f, art, bindir, log, "no-pr")
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert len([x for x in log.read_text().splitlines() if x == "pr create"]) == 1


@pytest.mark.skipif(os.name == "nt", reason="POSIX fresh-clone integration")
def test_review_pending_state_push_rejected_fresh_clone(tmp_path):
    repo, art, bindir, log = setup(tmp_path)
    bare = tmp_path / "remote.git"
    hook = bare / "hooks/pre-receive"
    hook.write_text("#!/bin/sh\nn=$(cat .push-count 2>/dev/null || echo 0)\nn=$((n+1))\necho $n > .push-count\nif [ $n -le 2 ]; then exit 0; fi\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    assert run(repo, art, bindir, log, "no-pr").returncode == 1
    hook.unlink()
    remote = subprocess.check_output(["git", "show", "fix/t:automation/state/tasks.json"], cwd=bare, text=True)
    assert '"status": "PUBLISHING"' in remote
    f = fresh(bare, tmp_path)
    r2 = run(f, art, bindir, log, "existing")
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert len([x for x in log.read_text().splitlines() if x == "pr create"]) == 1


@pytest.mark.skipif(os.name == "nt", reason="POSIX fresh-clone integration")
def test_review_pending_state_push_accepted_client_error_fresh_clone(tmp_path):
    repo, art, bindir, log = setup(tmp_path)
    wrap = push_wrapper(tmp_path, 3)
    r = run(repo, art, bindir, log, "no-pr", wrap)
    assert r.returncode == 0, r.stdout + r.stderr
    bare = tmp_path / "remote.git"
    remote = subprocess.check_output(["git", "show", "fix/t:automation/state/tasks.json"], cwd=bare, text=True)
    assert '"status": "REVIEW_PENDING"' in remote
    f = fresh(bare, tmp_path)
    r2 = run(f, art, bindir, log, "existing")
    assert r2.returncode == 0
    assert len([x for x in log.read_text().splitlines() if x == "pr create"]) == 1
