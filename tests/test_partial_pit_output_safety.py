"""Safety tests for explicitly isolated partial PIT price outputs."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "tools" / "research" / "refresh_sp500_pit_prices.py"
SPEC = importlib.util.spec_from_file_location("refresh_sp500_pit_prices_under_test", SCRIPT)
assert SPEC and SPEC.loader
refresh_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(refresh_module)


def test_partial_output_rejects_default_stock_path(monkeypatch, tmp_path):
    monkeypatch.setattr(
        refresh_module,
        "refresh",
        lambda args: pytest.fail("refresh must not run when default paths are used"),
    )
    with pytest.raises(SystemExit) as exc:
        refresh_module.main([
            "--allow-partial-output",
            "--stocks", str(refresh_module.DEFAULT_STOCKS),
            "--spy", str(tmp_path / "isolated_spy.csv"),
        ])
    assert exc.value.code == 2


def test_partial_output_rejects_default_spy_path(monkeypatch, tmp_path):
    monkeypatch.setattr(
        refresh_module,
        "refresh",
        lambda args: pytest.fail("refresh must not run when default paths are used"),
    )
    with pytest.raises(SystemExit) as exc:
        refresh_module.main([
            "--allow-partial-output",
            "--stocks", str(tmp_path / "isolated_stocks.csv"),
            "--spy", str(refresh_module.DEFAULT_SPY),
        ])
    assert exc.value.code == 2


def test_partial_output_accepts_two_isolated_paths(monkeypatch, tmp_path):
    captured = {}

    def fake_refresh(args):
        captured["args"] = args
        return {"status": "FAIL"}

    monkeypatch.setattr(refresh_module, "refresh", fake_refresh)
    stocks = tmp_path / "isolated_stocks.csv"
    spy = tmp_path / "isolated_spy.csv"
    audit = tmp_path / "isolated_audit.json"

    assert refresh_module.main([
        "--allow-partial-output",
        "--stocks", str(stocks),
        "--spy", str(spy),
        "--audit", str(audit),
    ]) == 0
    args = captured["args"]
    assert args.allow_partial_output is True
    assert args.stocks == stocks
    assert args.spy == spy
