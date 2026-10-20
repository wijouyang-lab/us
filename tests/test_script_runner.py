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
    r = subprocess.run(
        [sys.executable, path],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    detail = (r.stdout or "") + (r.stderr or "")
    assert r.returncode == 0, f"{script} 退出码 {r.returncode}\n{detail[-2000:]}"
