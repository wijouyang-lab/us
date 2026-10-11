"""买入决策前置到 scan 的 flag 门控测试（--buy-only / --no-buy）。

只验证 run() 的"调用分支"：
  · buy_only=True  → 跳过 process_sells，仅跑 process_buys
  · no_buy=True    → 跳过 process_buys，其余（含 process_sells）照常
  · 默认（两者均 False）→ process_sells 与 process_buys 都跑，与改动前逐字节一致

不重算盈亏、不联网（offline=True）。process_* 用 mock 拦截，仅断言调用次数。
"""
import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_dex():
    spec = importlib.util.spec_from_file_location(
        "portfolio_50000_buytest", REPO_ROOT / "portfolio_50000.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DEX = _load_dex()

_CSV_FILES = [
    "trade_history.csv",
    "portfolio_50000_positions.csv",
    "portfolio_50000_transactions.csv",
    "portfolio_50000_history.csv",
]


@pytest.fixture
def fake_dir(tmp_path):
    for f in _CSV_FILES:
        (tmp_path / f).write_text("")
    return tmp_path


def _run(fake_dir, **kwargs):
    with patch.object(DEX, "process_sells") as m_sells, \
         patch.object(DEX, "process_buys") as m_buys:
        m_sells.return_value = []
        m_buys.return_value = []
        DEX.run(fake_dir, offline=True, **kwargs)
        return m_sells, m_buys


def test_buy_only_runs_only_buys(fake_dir):
    """buy_only=True → 只跑 process_buys，不跑 process_sells。"""
    m_sells, m_buys = _run(fake_dir, buy_only=True)
    m_buys.assert_called_once()
    m_sells.assert_not_called()


def test_no_buy_skips_buys(fake_dir):
    """no_buy=True → 跳过 process_buys，process_sells 照常。"""
    m_sells, m_buys = _run(fake_dir, no_buy=True)
    m_buys.assert_not_called()
    m_sells.assert_called_once()


def test_default_runs_both(fake_dir):
    """默认（buy_only=False, no_buy=False）→ 两者都跑，与改动前一致。"""
    m_sells, m_buys = _run(fake_dir)
    m_sells.assert_called_once()
    m_buys.assert_called_once()


def test_buy_only_skips_sells(fake_dir):
    """关键：buy_only=True 时 process_sells 不被调用。"""
    m_sells, m_buys = _run(fake_dir, buy_only=True)
    m_sells.assert_not_called()


def test_no_buy_skips_buys_key(fake_dir):
    """关键：no_buy=True 时 process_buys 不被调用。"""
    m_sells, m_buys = _run(fake_dir, no_buy=True)
    m_buys.assert_not_called()
