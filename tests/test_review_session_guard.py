# -*- coding: utf-8 -*-
"""Regression tests for Review trading-session idempotency (P0-2)."""

import json
import threading
import time

import pytest

import review_session_guard as guard_mod
from review_session_guard import ReviewSessionGuard


SESSION = "2026-10-19"


def _seed(root):
    (root / "trade_history.csv").write_text("Date,Ticker,Status\n2026-10-19,AAA,Active\n", encoding="utf-8")
    (root / "review_history.csv").write_text("Review_Date,Ticker\n2026-10-19,AAA\n", encoding="utf-8")


def _pending(root, ticker="AAA"):
    day = SESSION.replace("-", "")
    path = root / ("us_stocks_pending_%s.csv" % day)
    path.write_text(
        "Date,Ticker,Tag,Name\n%s,%s,Core_Dragon,%s Inc\n" % (SESSION, ticker, ticker),
        encoding="utf-8",
    )
    return path


def test_same_session_twice_is_skipped(tmp_path):
    _seed(tmp_path)
    _pending(tmp_path)
    g1 = ReviewSessionGuard(tmp_path)
    d1 = g1.begin(SESSION)
    assert d1.skip is False
    g1.mark_success(SESSION)
    g1.release()

    g2 = ReviewSessionGuard(tmp_path)
    d2 = g2.begin(SESSION)
    g2.release()
    assert d2.skip is True
    assert "指纹未变化" in d2.reason


def test_new_pending_after_success_forces_safe_rerun(tmp_path):
    _seed(tmp_path)
    _pending(tmp_path, "AAA")
    g1 = ReviewSessionGuard(tmp_path)
    g1.begin(SESSION)
    g1.mark_success(SESSION)
    g1.release()

    _pending(tmp_path, "BBB")
    g2 = ReviewSessionGuard(tmp_path)
    d2 = g2.begin(SESSION)
    g2.release()
    assert d2.skip is False
    assert "已变化" in d2.reason


def test_failed_first_run_has_no_marker_and_can_recover(tmp_path):
    _seed(tmp_path)
    _pending(tmp_path)
    g1 = ReviewSessionGuard(tmp_path)
    d1 = g1.begin(SESSION)
    assert d1.skip is False
    # Simulate a partial write, then a crash before mark_success.
    (tmp_path / "trade_history.csv").write_text(
        "Date,Ticker,Status\n2026-10-19,AAA,Stop_Loss_Hit\n", encoding="utf-8"
    )
    g1.release()
    assert not (tmp_path / guard_mod.MARKER_NAME).exists()

    g2 = ReviewSessionGuard(tmp_path)
    d2 = g2.begin(SESSION)
    assert d2.skip is False
    assert "无成功标记" in d2.reason
    g2.mark_success(SESSION)
    g2.release()
    assert (tmp_path / guard_mod.MARKER_NAME).exists()


def test_new_trading_day_runs(tmp_path):
    _seed(tmp_path)
    _pending(tmp_path)
    g1 = ReviewSessionGuard(tmp_path)
    g1.begin(SESSION)
    g1.mark_success(SESSION)
    g1.release()

    g2 = ReviewSessionGuard(tmp_path)
    d2 = g2.begin("2026-10-20")
    g2.release()
    assert d2.skip is False
    assert "新的交易日" in d2.reason


def test_two_concurrent_requests_only_one_marks_success(tmp_path):
    _seed(tmp_path)
    _pending(tmp_path)
    acquired = threading.Event()
    result = {}
    errors = []

    def first():
        try:
            g = ReviewSessionGuard(tmp_path, lock_timeout=10)
            d = g.begin(SESSION)
            acquired.set()
            time.sleep(0.2)
            g.mark_success(SESSION)
            g.release()
            result["first"] = d.skip
        except Exception as exc:  # pragma: no cover
            errors.append(exc)
            acquired.set()

    def second():
        try:
            g = ReviewSessionGuard(tmp_path, lock_timeout=10)
            d = g.begin(SESSION)
            g.release()
            result["second"] = d.skip
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    t1 = threading.Thread(target=first)
    t2 = threading.Thread(target=second)
    t1.start()
    acquired.wait(timeout=5)
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)

    assert not errors
    assert result["first"] is False
    assert result["second"] is True


def test_mark_cli_refuses_without_ready_flag(tmp_path, monkeypatch):
    _seed(tmp_path)
    _pending(tmp_path)
    rc = guard_mod.main(["mark", "--root", str(tmp_path), "--session", SESSION])
    assert rc == 1
    assert not (tmp_path / guard_mod.MARKER_NAME).exists()

    (tmp_path / ".review_session_ready").write_text(SESSION, encoding="utf-8")
    rc2 = guard_mod.main(["mark", "--root", str(tmp_path), "--session", SESSION])
    assert rc2 == 0
    marker = json.loads((tmp_path / guard_mod.MARKER_NAME).read_text(encoding="utf-8"))
    assert marker["session_date"] == SESSION
    assert marker["status"] == "success"


def test_marker_remains_valid_after_pending_is_renamed_to_processed(tmp_path):
    _seed(tmp_path)
    pending = _pending(tmp_path)
    g1 = ReviewSessionGuard(tmp_path)
    g1.begin(SESSION)
    pending.rename(str(pending) + ".processed")
    g1.mark_success(SESSION)
    g1.release()

    g2 = ReviewSessionGuard(tmp_path)
    d2 = g2.begin(SESSION)
    g2.release()
    assert d2.skip is True


def test_invalid_marker_is_treated_as_incomplete(tmp_path):
    _seed(tmp_path)
    _pending(tmp_path)
    (tmp_path / guard_mod.MARKER_NAME).write_text("{not-json", encoding="utf-8")
    g = ReviewSessionGuard(tmp_path)
    d = g.begin(SESSION)
    g.release()
    assert d.skip is False
