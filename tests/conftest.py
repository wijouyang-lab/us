# -*- coding: utf-8 -*-
"""pytest 兼容层（conftest）：阻止脚本式测试文件在 collection 阶段被 import。

脚本式测试文件（test_dashboard_data_stability.py 等）是"线性脚本"：
模块级执行 + 尾部 sys.exit(0/1)。它们无法被 pytest 以函数粒度收集，
且 import 时触发 SystemExit 会导致 INTERNALERROR。

通过 collect_ignore 跳过这些文件的 import，改由 test_script_runner.py
以 subprocess 方式运行（退出码 0 = PASS）。
"""
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 脚本式测试文件（模块级执行 + sys.exit，无法函数级收集）
SCRIPT_TESTS = [
    "test_dashboard_data_stability.py",
    "test_dashboard_runtime.py",
    "test_event_key_p2.py",
    "test_milestone_win_rate.py",
    "test_options_reward_risk.py",
    "test_p05_repair_regression.py",
    "test_p3_5_rec_price_repair.py",
    "test_p3_data_quality.py",
    "test_portfolio_50000.py",
    "test_review_dashboard_fields.py",
]

# 阻止 pytest 在 collection 阶段 import 这些脚本式文件（模块级 sys.exit
# 会触发 SystemExit → INTERNALERROR）。它们改由 test_script_runner.py 以 subprocess 运行。
collect_ignore = SCRIPT_TESTS
