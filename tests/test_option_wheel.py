# -*- coding: utf-8 -*-
"""期权 Wheel（CSP → CC）L2 模块测试 —— flag 关闭时惰性、无副作用。

覆盖 OPTIONS_WHEEL_DESIGN.md §附 L2 草稿的 5 个用例：
  1. 卖 CSP 后现金冻结正确
  2. 被行权后持仓正确转换
  3. 卖 CC 要求正股 ≥ 100
  4. 单日上限 2 张
  5. 硬性禁止策略（Naked Call）被拒绝
外加：flag 关闭零副作用、白名单校验。
"""
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import option_wheel as ow  # 独立模块，无守卫，可直接导入


@pytest.fixture
def enabled(monkeypatch):
    """开启 ENABLE_OPTIONS_WHEEL 并 mock 权利金取值（避免打真实 API）。"""
    monkeypatch.setenv("ENABLE_OPTIONS_WHEEL", "1")
    monkeypatch.setattr(ow, "_get_option_quote", lambda *a, **k: 1.5)
    yield


@pytest.fixture
def fresh_ledger(tmp_path, monkeypatch):
    """把执行账本重定向到临时目录，隔离测试产物。"""
    monkeypatch.setattr(ow, "LEDGER", str(tmp_path / "option_positions.csv"))
    yield tmp_path


# ---------------------------------------------------------------------------
# 0. flag 关闭 → 零副作用（本模块未激活，无调用点）
# ---------------------------------------------------------------------------
def test_flag_off_sell_csp_inert(monkeypatch, fresh_ledger):
    monkeypatch.delenv("ENABLE_OPTIONS_WHEEL", raising=False)
    assert ow.sell_csp("XYZ", 100.0, "2026-11-15", 105.0) is None
    assert not (fresh_ledger / "option_positions.csv").exists()  # 未写账本


def test_flag_off_wheel_status_none(monkeypatch):
    monkeypatch.delenv("ENABLE_OPTIONS_WHEEL", raising=False)
    assert ow.wheel_status() is None


def test_flag_off_check_assignment_empty(monkeypatch):
    monkeypatch.delenv("ENABLE_OPTIONS_WHEEL", raising=False)
    assert ow.check_assignment([{"kind": "PUT", "status": "OPEN", "expiry": "2020-01-01",
                                 "strike": 100, "ticker": "XYZ"}], lambda t: 90) == []


# ---------------------------------------------------------------------------
# 白名单 / 黑名单校验（用例 5 的单元级拒绝分支）
# ---------------------------------------------------------------------------
def test_whitelist_allows_csp_cc():
    assert ow.is_strategy_allowed("CSP") is True
    assert ow.is_strategy_allowed("CC") is True
    assert ow.is_strategy_allowed("csp") is True   # 大小写不敏感


def test_forbidden_naked_call_rejected():
    # 硬性禁止策略一律拒绝（Naked Call/Put/Strangle/Straddle）
    for s in ("NAKED_CALL", "NAKED_PUT", "STRANGLE", "STRADDLE"):
        assert ow.is_strategy_allowed(s) is False
    # 不在白名单的其它策略也拒绝
    assert ow.is_strategy_allowed("LONG_CALL") is False
    assert ow.is_strategy_allowed("") is False


# ---------------------------------------------------------------------------
# 用例 1：卖 CSP 后现金冻结正确
# ---------------------------------------------------------------------------
def test_sell_csp_cash_collateral(enabled, fresh_ledger):
    row = ow.sell_csp("XYZ", 100.0, "2026-11-15", 105.0)
    assert row is not None
    # 担保现金 = strike * 100 * contracts(=1)
    assert row["cash_collateral"] == 100.0 * 100
    assert row["kind"] == "PUT"
    assert row["status"] == "OPEN"
    # 账本已写入一行
    ledger = fresh_ledger / "option_positions.csv"
    assert ledger.exists()
    lines = ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2   # 表头 + 1 行
    assert "10000.0" in lines[1]   # cash_collateral 透传


# ---------------------------------------------------------------------------
# 用例 2：被行权后持仓正确转换
# ---------------------------------------------------------------------------
def test_check_assignment_put_assigned(enabled):
    positions = [
        {"ticker": "XYZ", "kind": "PUT", "status": "OPEN", "strike": 100.0,
         "expiry": "2020-01-01", "contracts": 1},
    ]
    # 实时价 95 ≤ strike 100 → 价内被行权
    events = ow.check_assignment(positions, lambda t: 95.0)
    assert len(events) == 1
    ev = events[0]
    assert ev["type"] == "PUT_ASSIGNED"
    assert ev["shares"] == 100           # 100 * 1 张
    assert ev["price"] == 100.0
    # 原行状态变 ASSIGNED、担保现金释放（assigned_shares 记录）
    assert positions[0]["status"] == "ASSIGNED"
    assert positions[0]["assigned_shares"] == 100


def test_check_assignment_put_expired_otm(enabled):
    positions = [
        {"ticker": "XYZ", "kind": "PUT", "status": "OPEN", "strike": 100.0,
         "expiry": "2020-01-01", "contracts": 1},
    ]
    # 实时价 105 > strike 100 → 价外过期
    events = ow.check_assignment(positions, lambda t: 105.0)
    assert events[0]["type"] == "EXPIRED"
    assert positions[0]["status"] == "EXPIRED"
    assert positions[0]["assigned_shares"] == 0


# ---------------------------------------------------------------------------
# 用例 3：卖 CC 要求正股 ≥ 100
# ---------------------------------------------------------------------------
def test_sell_covered_call_requires_100_shares(enabled, fresh_ledger):
    # 正股仅 50 股 → 裸卖 Call 被拒
    with pytest.raises(RuntimeError, match="需正股 ≥ 100"):
        ow.sell_covered_call("XYZ", 110.0, "2026-11-15", long_shares=50)
    # 正股 200 股 → 成功（CALL 行，无担保现金）
    row = ow.sell_covered_call("XYZ", 110.0, "2026-11-15", long_shares=200)
    assert row is not None
    assert row["kind"] == "CALL"
    assert row["cash_collateral"] == 0.0


# ---------------------------------------------------------------------------
# 用例 4：单日上限 2 张
# ---------------------------------------------------------------------------
def test_daily_write_limit(enabled, fresh_ledger):
    for i in range(2):
        r = ow.sell_csp(f"T{i}", 100.0 + i, "2026-11-15", 105.0)
        assert r is not None
    # 第 3 张触发单日上限
    with pytest.raises(RuntimeError, match="单日写入已达上限 2 张"):
        ow.sell_csp("T2", 102.0, "2026-11-15", 105.0)


# ---------------------------------------------------------------------------
# 用例 5（补充）：Naked Call 经白名单显式拒绝（拒绝分支被命中）
# ---------------------------------------------------------------------------
def test_forbidden_strategy_rejected_branch():
    # NAKED_CALL 在 FORBIDDEN_STRATEGIES，is_strategy_allowed 返回 False
    assert "NAKED_CALL" in ow.FORBIDDEN_STRATEGIES
    assert ow.is_strategy_allowed("NAKED_CALL") is False
