import sys
import time
from pathlib import Path

from tools.automation.headless import HeadlessRunner


def test_stdout_limit_streams_and_truncates(tmp_path):
    script = tmp_path / "big.py"
    script.write_text("import sys\nsys.stdout.write('x' * 2000000)\n", encoding="utf-8")
    out = HeadlessRunner([sys.executable, str(script)], max_output_bytes=1000, timeout=20).run("p", tmp_path / "log")
    assert out["output_limit_exceeded"] is True
    assert out["returncode"] == 125
    assert len((tmp_path / "log").read_text(encoding="utf-8")) <= 1000


def test_stderr_is_merged_and_bounded(tmp_path):
    script = tmp_path / "err.py"
    script.write_text("import sys\nsys.stderr.write('e' * 2000000)\n", encoding="utf-8")
    out = HeadlessRunner([sys.executable, str(script)], max_output_bytes=512, timeout=20).run("p", tmp_path / "log")
    assert out["output_limit_exceeded"] is True
    assert len((tmp_path / "log").read_text(encoding="utf-8")) <= 512


def test_timeout_terminates_and_returns_124(tmp_path):
    script = tmp_path / "sleep.py"
    script.write_text("import time\nprint('started', flush=True)\ntime.sleep(30)\n", encoding="utf-8")
    out = HeadlessRunner([sys.executable, str(script)], max_output_bytes=1000, timeout=1).run("p", tmp_path / "log")
    assert out["timed_out"] is True
    assert out["returncode"] == 124


def test_normal_small_output(tmp_path):
    script = tmp_path / "ok.py"
    script.write_text("print('{\"type\":\"final\",\"text\":\"ok\"}')\n", encoding="utf-8")
    out = HeadlessRunner([sys.executable, str(script)], max_output_bytes=1000, timeout=10).run("p", tmp_path / "log")
    assert out["returncode"] == 0
    assert out["final"] == "ok"

def test_grandchild_is_terminated_when_parent_exits(tmp_path):
    import os, time
    init = tmp_path / "parent.py"
    pidfile = tmp_path / "grandchild.pid"
    init.write_text(
        "import subprocess,sys,time\n"
        "p=subprocess.Popen([sys.executable,'-c','import sys,time\\nwhile True:\\n sys.stdout.write(\\\"x\\\"*4096); sys.stdout.flush()'])\n"
        f"open({str(pidfile)!r},'w').write(str(p.pid))\n"
        "time.sleep(0.2)\n",
        encoding="utf-8",
    )
    out = HeadlessRunner([sys.executable, str(init)], max_output_bytes=5000, timeout=10).run("p", tmp_path / "log")
    assert out["returncode"] in {0, 125}
    time.sleep(0.3)
    pid = int(pidfile.read_text(encoding="utf-8"))
    try:
        os.kill(pid, 0)
    except OSError:
        pass
    else:
        os.kill(pid, 9)
        raise AssertionError("grandchild survived")

import os as _os
import pytest

@pytest.mark.skipif(_os.name == "nt", reason="POSIX killpg")
def test_kill_failure_is_reported(monkeypatch):
    from tools.automation import headless
    class P:
        pid = 123
        def kill(self):
            pass
    def denied(*args, **kwargs):
        raise PermissionError("denied")
    monkeypatch.setattr(headless.os, "killpg", denied)
    monkeypatch.setattr(headless.os, "getpgid", lambda pid: 123)
    assert headless._kill_tree(P(), 123) is False

def test_cleanup_failure_is_not_success(tmp_path, monkeypatch):
    import sys
    from tools.automation import headless
    monkeypatch.setattr(headless, "_kill_tree", lambda *a, **k: False)
    script = tmp_path / "ok.py"
    script.write_text("print('ok')\n", encoding="utf-8")
    out = HeadlessRunner([sys.executable, str(script)], max_output_bytes=1000, timeout=10).run("p", tmp_path / "log")
    assert out["returncode"] == 126
    assert out["cleanup_failed"] is True
