# -*- coding: utf-8 -*-
"""BLS CPI 同比计算：必须匹配「同一日历月」，不能按位置回退。

历史 bug：BLS 序列缺月（如政府停摆导致某月未发布）时，``parsed[-13]``
会拿到 11 个月前的基数，把 3.7% 算成 4.0%、2.6% 算成 2.79%。

这里用 AST 抽取 ``_calc_yoy_from_series`` 单独执行，避免 import scan.py 的
重型依赖（pandas_ta / yfinance）。
"""
import ast
import os
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SRC = (_REPO_ROOT / "scan.py").read_text(encoding="utf-8")
_TREE = ast.parse(_SRC)
_NODE = next(n for n in ast.walk(_TREE)
             if isinstance(n, ast.FunctionDef) and n.name == "_calc_yoy_from_series")
_NS = {"pd": pd}
exec(ast.get_source_segment(_SRC, _NODE), _NS)
calc = _NS["_calc_yoy_from_series"]


def _p(s):
    return pd.Timestamp(s)


def test_continuous_series_matches_exact_month():
    parsed = [(_p("2025-09-01"), 324.91), (_p("2026-09-01"), 336.94)]
    assert calc(parsed) == 3.7 or abs(calc(parsed) - 3.7) < 0.01


def test_missing_month_does_not_shift_base():
    """缺一个月时，仍用 2025-09 作基数（3.7%），而不是 2025-08（4.0%）。"""
    parsed = [
        (_p("2025-08-01"), 323.98),
        (_p("2025-09-01"), 324.91),
        (_p("2025-11-01"), 326.00),   # 缺 2025-10
        (_p("2026-09-01"), 336.94),
    ]
    val = calc(parsed)
    assert abs(val - 3.7) < 0.01, val
    assert abs(val - 4.0) > 0.1


def test_core_cpi_gap_case():
    # 核心 CPI：2025-09 基数应得 ~2.6%；用 2025-08 会算成 ~2.79%
    parsed = [
        (_p("2025-08-01"), 329.70),
        (_p("2025-09-01"), 330.31),
        (_p("2025-11-01"), 331.00),
        (_p("2026-09-01"), 338.90),
    ]
    val = calc(parsed)
    assert abs(val - 2.6) < 0.05, val


def test_missing_base_month_returns_none():
    parsed = [(_p("2025-10-01"), 325.5), (_p("2026-09-01"), 336.94)]
    assert calc(parsed) is None


def test_empty_or_invalid_base():
    assert calc([]) is None
    assert calc([(_p("2025-09-01"), 0), (_p("2026-09-01"), 336.94)]) is None
