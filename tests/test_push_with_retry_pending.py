# -*- coding: utf-8 -*-
"""Regression tests for Review pending-safe push guard.

These tests use isolated temporary bare/working repos and the real
tools/ci/push_with_retry.sh.  No production remote or data is touched.
"""

import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools" / "ci" / "push_with_retry.sh"
GIT_BASH = shutil.which("bash") or r"C:\Program Files\Git\bin\bash.exe"


def run(cwd, *args, check=True):
    proc = subprocess.run(
        ["git"] + list(args), cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if check and proc.returncode != 0:
        raise RuntimeError("git %s failed\n%s\n%s" % (" ".join(args), proc.stdout, proc.stderr))
    return proc


def setup(tmp_path):
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    run(tmp_path, "init", "--bare", "--initial-branch=main", str(remote))
    run(tmp_path, "-c", "core.autocrlf=false", "clone", str(remote), str(seed))
    run(seed, "config", "user.email", "sim@example.com")
    run(seed, "config", "user.name", "sim")
    run(seed, "config", "core.autocrlf", "false")
    (seed / "us_stocks_pending_20261020.csv").write_text(
        "Date,Ticker,Tag\n2026-10-20,AAA,Core_Dragon\n", encoding="utf-8"
    )
    (seed / "trade_history.csv").write_text("Date,Ticker\n", encoding="utf-8")
    run(seed, "add", ".")
    run(seed, "commit", "-m", "seed")
    run(seed, "push", "origin", "main")
    return remote, seed


def clone(tmp_path, remote, name):
    path = tmp_path / name
    run(tmp_path, "-c", "core.autocrlf=false", "clone", str(remote), str(path))
    run(path, "config", "user.email", "sim@example.com")
    run(path, "config", "user.name", "sim")
    run(path, "config", "core.autocrlf", "false")
    return path


def review_commit(path):
    pending = path / "us_stocks_pending_20261020.csv"
    pending.rename(path / "us_stocks_pending_20261020.csv.processed")
    (path / "trade_history.csv").write_text(
        "Date,Ticker\n2026-10-20,AAA\n", encoding="utf-8"
    )
    run(path, "add", "trade_history.csv", "us_stocks_pending_20261020.csv.processed")
    # Literal pathspec matches the tracked original even after rename.
    run(path, "rm", "-f", "us_stocks_pending_*.csv")
    run(path, "commit", "-m", "review: ledger+rename")


def scan_append(path, ticker="BBB"):
    pending = path / "us_stocks_pending_20261020.csv"
    with pending.open("a", encoding="utf-8") as fh:
        fh.write("2026-10-20,%s,Core_Dragon\n" % ticker)
    run(path, "add", pending.name)
    run(path, "commit", "-m", "scan: append")
    run(path, "push", "origin", "main")


def scan_new_date(path, date="2026-10-21", ticker="CCC"):
    pending = path / ("us_stocks_pending_%s.csv" % date.replace("-", ""))
    pending.write_text("Date,Ticker,Tag\n%s,%s,Core_Dragon\n" % (date, ticker), encoding="utf-8")
    run(path, "add", pending.name)
    run(path, "commit", "-m", "scan: new date")
    run(path, "push", "origin", "main")


def remote_show(remote, path):
    proc = run(remote, "--git-dir", str(remote), "show", "main:%s" % path, check=False)
    return proc.stdout if proc.returncode == 0 else None


def remote_exists(remote, path):
    proc = run(remote, "--git-dir", str(remote), "cat-file", "-e", "main:%s" % path, check=False)
    return proc.returncode == 0


def run_guard(cwd):
    return subprocess.run(
        [GIT_BASH, str(SCRIPT), "2", "0", "1"],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


@pytest.mark.skipif(not Path(GIT_BASH).exists(), reason="bash not available")
def test_normal_review_push_is_allowed(tmp_path):
    remote, _ = setup(tmp_path)
    review = clone(tmp_path, remote, "review")
    review_commit(review)
    result = run_guard(review)
    assert result.returncode == 0, result.stdout + result.stderr
    assert remote_exists(remote, "us_stocks_pending_20261020.csv.processed")
    assert not remote_exists(remote, "us_stocks_pending_20261020.csv")
    assert "push ok" in result.stdout


@pytest.mark.skipif(not Path(GIT_BASH).exists(), reason="bash not available")
def test_same_date_scan_append_blocks_review_push(tmp_path):
    remote, _ = setup(tmp_path)
    review = clone(tmp_path, remote, "review")
    scan = clone(tmp_path, remote, "scan")
    review_commit(review)
    scan_append(scan, "BBB")

    result = run_guard(review)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "remote us_stocks_pending_20261020.csv changed" in result.stdout
    pending = remote_show(remote, "us_stocks_pending_20261020.csv")
    assert pending is not None and "AAA" in pending and "BBB" in pending
    assert not remote_exists(remote, "us_stocks_pending_20261020.csv.processed")


@pytest.mark.skipif(not Path(GIT_BASH).exists(), reason="bash not available")
def test_new_date_pending_blocks_review_push(tmp_path):
    remote, _ = setup(tmp_path)
    review = clone(tmp_path, remote, "review")
    scan = clone(tmp_path, remote, "scan")
    review_commit(review)
    scan_new_date(scan)

    result = run_guard(review)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "has no local .processed" in result.stdout
    assert remote_exists(remote, "us_stocks_pending_20261021.csv")
    assert remote_exists(remote, "us_stocks_pending_20261020.csv")
    assert not remote_exists(remote, "us_stocks_pending_20261020.csv.processed")
