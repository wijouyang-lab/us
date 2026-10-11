# -*- coding: utf-8 -*-
"""UNIT_IDS 容量扩展回归测试（#4 浮动 3-5 只）。

仅验证常量定义与 next_free_unit 的分配逻辑；不运行完整 process_buys
（集成路径由 test_portfolio_50000.py 覆盖）。

要点：
  - UNIT_IDS 扩到 10 个（U001~U010），只加不删，现有 U001-U004 不动。
  - 现有 4 只持仓（OPEN，占用 U001-U004）的 Unit_ID 分配不被重排。
  - 第 5 只买入时 next_free_unit 返回 U005（"浮动 3-5 只"的 5 只可达）。
"""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location("pfmod_unitids", REPO / "portfolio_50000.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_unit_ids_expanded_to_ten_and_first_four_preserved():
    pf = _load()
    assert len(pf.UNIT_IDS) == 10, pf.UNIT_IDS
    assert pf.UNIT_IDS[:4] == ["U001", "U002", "U003", "U004"], pf.UNIT_IDS[:4]
    assert pf.UNIT_IDS[4:] == ["U005", "U006", "U007", "U008", "U009", "U010"], pf.UNIT_IDS[4:]


def test_fifth_position_gets_u005_when_first_four_used():
    pf = _load()
    # 现有 4 只持仓分别占用 U001-U004（OPEN）
    positions = [
        {"Status": "OPEN", "Unit_ID": "U001", "Ticker": "A"},
        {"Status": "OPEN", "Unit_ID": "U002", "Ticker": "B"},
        {"Status": "OPEN", "Unit_ID": "U003", "Ticker": "C"},
        {"Status": "OPEN", "Unit_ID": "U004", "Ticker": "D"},
    ]
    # 第 5 只买入应拿到 U005
    assert pf.next_free_unit(positions) == "U005"
    # 现有 4 只的 Unit_ID 分配不被重排（扩展只加不删）
    assigned = {str(p["Unit_ID"]).upper() for p in positions}
    assert assigned == {"U001", "U002", "U003", "U004"}


def test_next_free_unit_returns_none_when_all_ten_used():
    pf = _load()
    # 全部 10 个 Unit 均被 OPEN 持仓占用 → 容量饱和
    positions = [
        {"Status": "OPEN", "Unit_ID": uid, "Ticker": f"T{i}"}
        for i, uid in enumerate(pf.UNIT_IDS)
    ]
    assert pf.next_free_unit(positions) is None


def test_next_free_unit_skips_non_open_units():
    pf = _load()
    # 已平仓（非 OPEN）的 U005 不应占用名额
    positions = [{"Status": "CLOSED", "Unit_ID": "U005", "Ticker": "X"}]
    assert pf.next_free_unit(positions) == "U001"
