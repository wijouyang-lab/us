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
