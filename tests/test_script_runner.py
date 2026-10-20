# -*- coding: utf-8 -*-
"""以 subprocess 运行脚本式测试文件（模块级执行 + sys.exit），纳入 pytest。

脚本式测试文件由 conftest.py 的 collect_ignore 跳过 import（避免 INTERNALERROR），
本文件以 subprocess 逐个运行它们，退出码 0 = PASS。
"""
import os
import subprocess
import sys

import pytest

from conftest import REPO_ROOT, SCRIPT_TESTS


@pytest.mark.parametrize("script", SCRIPT_TESTS)
def test_script(script):
    """以 subprocess 运行脚本式测试文件，退出码 0 视为通过。"""
    path = os.path.join(REPO_ROOT, "tests", script)
    env = os.environ.copy()
    # Script-style tests import modules via importlib.util.spec_from_file_location.
    # In that mode sys.path[0] can be tests/, so explicitly expose repo-root packages.
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (REPO_ROOT, existing_pythonpath) if part
    )
    r = subprocess.run(
        [sys.executable, path],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    detail = (r.stdout or "") + (r.stderr or "")
    assert r.returncode == 0, f"{script} 退出码 {r.returncode}\n{detail[-2000:]}"
