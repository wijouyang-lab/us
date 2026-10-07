# -*- coding: utf-8 -*-
"""Quant Dashboard 第一阶段（展示层）专项测试。

只验证 dashboard_export.build_quant() 与前端 Quant section / renderQuant() 的接入：
1. build_quant() 可执行；
2. build_quant() / dashboard_export.py 不 import 任何 quant 模块；
3. Quant 数据文件缺失时 Phase 1–7 输出真实状态（NOT_ENOUGH_DATA / DISABLED /
   SHADOW_DISABLED / V1_ACTIVE / V2_DISABLED / NOT_READY）；
4. 不产生任何虚假数字（IC / Sharpe / Return / Win Rate 等字段绝不出现）；
5. build_quant() 为纯函数，不改写任何现有 payload / 数据文件；
6. payload["quant"] schema 正常；
7. index.html 存在 Quant section；
8. Quant section 位于 Portfolio section 之后；
9. app.js 存在 renderQuant()；
10. 前端无数据时不会渲染虚假 Quant 数字。

本测试不 import 任何 quant 生产/计算模块，不联网、不写盘、不依赖真实行情。
"""
import json
import os
import re
import subprocess
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import dashboard_export as de  # noqa: E402


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def _walk_keys(obj, prefix=""):
    """递归产出所有 JSON 键（含路径），用于 schema / 虚假字段检查。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            full = f"{prefix}.{k}" if prefix else k
            yield full
            yield from _walk_keys(v, full)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_keys(v, f"{prefix}[{i}]")


def _build_in_empty_dir():
    with tempfile.TemporaryDirectory() as d:
        return de.build_quant(de.Path(d))


# ---------------------------------------------------------------------------
# 1. build_quant() 可执行，且是纯函数
# ---------------------------------------------------------------------------

def test_build_quant_runs_and_is_pure():
    q1 = _build_in_empty_dir()
    q2 = _build_in_empty_dir()
    assert isinstance(q1, dict)
    assert q1 == q2, "build_quant 应为确定性纯函数（同输入同输出）"


# ---------------------------------------------------------------------------
# 2. 不 import quant 模块
# ---------------------------------------------------------------------------

def test_dashboard_export_does_not_import_quant_modules():
    src = de.Path(de.__file__).read_text(encoding="utf-8")
    # dashboard_export.py 源码中不得出现任何 quant 模块导入
    assert not re.search(r"^\s*(import|from)\s+quant_\w+", src, re.MULTILINE), (
        "dashboard_export.py 不应 import 任何 quant 模块"
    )
    # 在【独立子进程】中只 import dashboard_export，确认进程内不会因此加载任何 quant 模块。
    # （不能在本测试进程内查 sys.modules：全量 pytest 下其它测试文件会 import quant 模块。）
    code = (
        "import sys; "
        "import dashboard_export; "
        "loaded = [n for n in sys.modules if n.startswith('quant_')]; "
        "assert not loaded, f'import dashboard_export 意外加载了 quant 模块: {loaded}'"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )
    assert r.returncode == 0, f"子进程校验失败：{r.stdout}{r.stderr}"


# ---------------------------------------------------------------------------
# 3. 空数据 → Phase 1–7 真实状态
# ---------------------------------------------------------------------------

def test_phases_status_when_no_data():
    q = _build_in_empty_dir()
    assert q["status"] == "RESEARCH"
    assert q["data_availability"] == "NOT_ENOUGH_DATA"

    assert q["factor_lab"]["status"] == "NOT_ENOUGH_DATA"
    assert q["backtest"]["status"] == "NOT_ENOUGH_DATA"
    assert q["validation"]["status"] == "NOT_ENOUGH_DATA"

    assert q["score_v2"]["status"] == "DISABLED"
    assert q["score_v2"]["enabled"] is False

    assert q["walk_forward"]["status"] == "NOT_ENOUGH_DATA"

    assert q["shadow"]["status"] == "SHADOW_DISABLED"
    assert q["shadow"]["enabled"] is False

    assert q["production"]["status"] == "V1_ACTIVE"
    assert q["production"]["active_version"] == "V1"
    assert q["production"]["v2_enabled"] is False
    assert q["production"]["v2_status"] == "DISABLED"
    assert q["production"]["production_gate"] == "NOT_READY"


# ---------------------------------------------------------------------------
# 4. 不产生虚假数字
# ---------------------------------------------------------------------------

def test_no_fabricated_metrics():
    q = _build_in_empty_dir()
    forbidden = ("ic", "sharpe", "win_rate", "winrate", "return", "pnl",
                 "profit", "quintile", "drawdown", "ann_return")
    for key in _walk_keys(q):
        kl = key.lower()
        for bad in forbidden:
            assert bad not in kl, f"出现疑似伪造指标键：{key}"


def test_factor_count_and_models_are_structural_only():
    q = _build_in_empty_dir()
    # 结构性数量（因子个数 / 持有期 / 模型个数）是允许的静态结构，不是伪造绩效
    assert q["factor_lab"]["factor_count"] == 8
    assert len(q["factor_lab"]["factors"]) == 8
    assert [h["label"] for h in q["backtest"]["horizons"]] == ["5D", "10D", "20D"]
    assert q["validation"]["combos"] == 72
    assert len(q["score_v2"]["models"]) == 3
    assert len(q["walk_forward"]["models"]) == 4  # 3 候选 + 1 基准


# ---------------------------------------------------------------------------
# 5. 不改写现有 payload（build_quant 只输出 quant 自己的键，且不写盘）
# ---------------------------------------------------------------------------

def test_build_quant_scoped_keys_only():
    q = _build_in_empty_dir()
    allowed = {
        "status", "data_availability", "note",
        "factor_lab", "backtest", "validation", "score_v2",
        "walk_forward", "shadow", "production",
    }
    assert set(q.keys()) == allowed
    # 不得夹带任何其它 dashboard 顶层键（stocks/review/portfolio/...）
    for other in ("stocks", "review", "portfolio", "options", "runtimes", "history", "market", "meta"):
        assert other not in q


def test_build_quant_does_not_write_files():
    with tempfile.TemporaryDirectory() as d:
        de.build_quant(de.Path(d))
        assert os.listdir(d) == [], "build_quant 不得在数据目录写任何文件"


# ---------------------------------------------------------------------------
# 6. schema 正常
# ---------------------------------------------------------------------------

def test_quant_schema_shape():
    q = _build_in_empty_dir()
    for key in ("factor_lab", "backtest", "validation", "score_v2",
                "walk_forward", "shadow", "production"):
        phase = q[key]
        assert isinstance(phase["phase"], int)
        assert isinstance(phase["label"], str) and phase["label"]
        assert isinstance(phase["status"], str) and phase["status"]
    # 关键字段存在且类型正确
    assert q["production"]["active_model"] == "CURRENT_EXISTING_QUANT_SCORE"
    assert isinstance(q["production"]["v2_enabled"], bool)
    assert isinstance(q["score_v2"]["enabled"], bool)
    assert isinstance(q["shadow"]["enabled"], bool)


# ---------------------------------------------------------------------------
# 7 / 8. index.html 存在 Quant section，且位于 Portfolio 之后
# ---------------------------------------------------------------------------

def test_index_has_quant_section_after_portfolio():
    html = de.Path(REPO_ROOT, "index.html").read_text(encoding="utf-8")
    assert 'id="quantSec"' in html
    assert "Quant / 量化研究" in html
    pi = html.index('id="portfolioSec"')
    qi = html.index('id="quantSec"')
    assert qi > pi, "Quant section 必须位于 Portfolio section 之后"


# ---------------------------------------------------------------------------
# 9. app.js 存在 renderQuant()
# ---------------------------------------------------------------------------

def test_app_js_has_render_quant():
    js = de.Path(REPO_ROOT, "app.js").read_text(encoding="utf-8")
    assert re.search(r"function renderQuant\s*\(\)", js)
    # renderDashboard 里必须在 renderPortfolio 之后调用 renderQuant
    assert re.search(r"renderPortfolio\(\);\s*\n\s*renderQuant\(\);", js), (
        "renderDashboard 应在 renderPortfolio() 之后调用 renderQuant()"
    )


# ---------------------------------------------------------------------------
# 10. 前端无数据时不渲染虚假 Quant 数字
# ---------------------------------------------------------------------------

def test_render_quant_has_no_fabricated_metrics():
    js = de.Path(REPO_ROOT, "app.js").read_text(encoding="utf-8")
    m = re.search(r"function renderQuant\s*\(\s*\)\s*\{", js)
    assert m, "找不到 renderQuant 定义"
    # 取到下一个顶层 function 之前作为函数体
    rest = js[m.start():]
    nxt = re.search(r"\n  function ", rest)
    body = rest[:nxt.start()] if nxt else rest
    for bad in ("Sharpe", "Win Rate", "IC =", "Return %", "annualized", "quintile"):
        assert bad not in body, f"renderQuant 函数体疑似渲染伪造指标：{bad}"


if __name__ == "__main__":
    # 支持脚本式直跑（pytest 之外）
    import traceback

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"[PASS] {t.__name__}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"[FAIL] {t.__name__}  {e}")
            traceback.print_exc()
    sys.exit(1 if failed else 0)
