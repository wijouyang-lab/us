# -*- coding: utf-8 -*-
"""Regression tests for Review trading-session idempotency (P0-2)."""

import json
import threading
import time

import pytest

import review_session_guard as guard_mod
from review_session_guard import ReviewSessionGuard


SESSION = "2026-10-20"


def _seed(root):
    (root / "trade_history.csv").write_text(
        "Date,Ticker,Status\n%s,AAA,Active\n" % SESSION, encoding="utf-8"
    )
    (root / "review_history.csv").write_text(
        "Review_Date,Ticker\n%s,AAA\n" % SESSION, encoding="utf-8"
    )


def _write_pending(root, date, ticker="AAA", tag="Core_Dragon", empty=False):
    day = date.replace("-", "")
    path = root / ("us_stocks_pending_%s.csv" % day)
    if empty:
        path.write_text("Date,Ticker,Tag,Name\n", encoding="utf-8")
        return path
    path.write_text(
        "Date,Ticker,Tag,Name\n%s,%s,%s,%s Inc\n" % (date, ticker, tag, ticker),
        encoding="utf-8",
    )
    return path


def _consume(path):
    target = path.with_name(path.name + ".processed")
    if target.exists():
        target.unlink()
    path.rename(target)
    return target


def _complete(root, session, pending_paths):
    guard = ReviewSessionGuard(root)
    decision = guard.begin(session)
    assert decision.skip is False
    for path in pending_paths:
        _consume(path)
    guard.mark_success(session)
    guard.release()
    return guard


def test_normal_success_then_same_session_skips(tmp_path):
    _seed(tmp_path)
    pending = _write_pending(tmp_path, SESSION)
    _complete(tmp_path, SESSION, [pending])

    guard = ReviewSessionGuard(tmp_path)
    decision = guard.begin(SESSION)
    guard.release()
    assert decision.skip is True
    assert "已成功处理" in decision.reason


def test_new_pending_after_success_forces_safe_rerun(tmp_path):
    _seed(tmp_path)
    first = _write_pending(tmp_path, SESSION, "AAA")
    _complete(tmp_path, SESSION, [first])

    second = _write_pending(tmp_path, SESSION, "BBB")
    guard = ReviewSessionGuard(tmp_path)
    decision = guard.begin(SESSION)
    guard.release()
    assert decision.skip is False
    assert "已变化" in decision.reason


def test_cross_date_pending_change_is_detected(tmp_path):
    """Session 10-20 must react to a 10-19 pending file change."""
    _seed(tmp_path)
    p19 = _write_pending(tmp_path, "2026-10-19", "OLD")
    p20 = _write_pending(tmp_path, SESSION, "AAA")
    _complete(tmp_path, SESSION, [p19, p20])

    # Same current-session file is untouched; only the older date changes.
    _write_pending(tmp_path, "2026-10-19", "OLD2")
    guard = ReviewSessionGuard(tmp_path)
    decision = guard.begin(SESSION)
    guard.release()
    assert decision.skip is False
    assert "已变化" in decision.reason


def test_cross_date_processed_change_is_detected(tmp_path):
    """An edited .processed file is also an input change, even with no .csv."""
    _seed(tmp_path)
    p19 = _write_pending(tmp_path, "2026-10-19", "OLD")
    p20 = _write_pending(tmp_path, SESSION, "AAA")
    processed19 = _consume(p19)
    _consume(p20)
    guard = ReviewSessionGuard(tmp_path)
    guard.begin(SESSION)
    guard.mark_success(SESSION)
    guard.release()

    with processed19.open("a", encoding="utf-8") as handle:
        handle.write("2026-10-19,NEW,Observation,NEW Inc\n")

    guard2 = ReviewSessionGuard(tmp_path)
    decision = guard2.begin(SESSION)
    guard2.release()
    assert decision.skip is False
    assert "已变化" in decision.reason


def test_unprocessed_pending_blocks_skip_even_if_fingerprint_matches(tmp_path):
    _seed(tmp_path)
    pending = _write_pending(tmp_path, SESSION)
    processed = _consume(pending)
    guard = ReviewSessionGuard(tmp_path)
    guard.begin(SESSION)
    guard.mark_success(SESSION)
    guard.release()

    # Simulate a crash after DB write but before the rename, by reversing it.
    processed.rename(pending)
    guard2 = ReviewSessionGuard(tmp_path)
    decision = guard2.begin(SESSION)
    guard2.release()
    assert decision.skip is False
    assert "未处理 pending" in decision.reason


def test_processing_failure_cannot_mark_success_and_retry_works(tmp_path):
    _seed(tmp_path)
    pending = _write_pending(tmp_path, SESSION)
    guard = ReviewSessionGuard(tmp_path)
    assert guard.begin(SESSION).skip is False

    # File remains .csv: this is the observable "processing failed" state.
    with pytest.raises(guard_mod.ReviewGuardError):
        guard.mark_success(SESSION)
    assert not (tmp_path / guard_mod.MARKER_NAME).exists()
    guard.release()

    # Retry: no success marker, so the next run executes; then complete it.
    retry = ReviewSessionGuard(tmp_path)
    assert retry.begin(SESSION).skip is False
    _consume(pending)
    retry.mark_success(SESSION)
    retry.release()

    guard3 = ReviewSessionGuard(tmp_path)
    assert guard3.begin(SESSION).skip is True
    guard3.release()


def test_new_trading_day_runs(tmp_path):
    _seed(tmp_path)
    pending = _write_pending(tmp_path, "2026-10-19")
    _complete(tmp_path, "2026-10-19", [pending])

    guard = ReviewSessionGuard(tmp_path)
    decision = guard.begin(SESSION)
    guard.release()
    assert decision.skip is False
    assert "新的交易日" in decision.reason


def test_two_concurrent_requests_only_one_marks_success(tmp_path):
    _seed(tmp_path)
    pending = _write_pending(tmp_path, SESSION)
    acquired = threading.Event()
    result = {}
    errors = []

    def first():
        try:
            guard = ReviewSessionGuard(tmp_path, lock_timeout=10)
            decision = guard.begin(SESSION)
            acquired.set()
            time.sleep(0.2)
            _consume(pending)
            guard.mark_success(SESSION)
            guard.release()
            result["first"] = decision.skip
        except Exception as exc:  # pragma: no cover
            errors.append(exc)
            acquired.set()

    def second():
        try:
            guard = ReviewSessionGuard(tmp_path, lock_timeout=10)
            decision = guard.begin(SESSION)
            guard.release()
            result["second"] = decision.skip
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


def test_mark_cli_refuses_without_ready_flag(tmp_path):
    _seed(tmp_path)
    pending = _write_pending(tmp_path, SESSION)
    rc = guard_mod.main(["mark", "--root", str(tmp_path), "--session", SESSION])
    assert rc == 1
    assert not (tmp_path / guard_mod.MARKER_NAME).exists()

    (tmp_path / ".review_session_ready").write_text(SESSION, encoding="utf-8")
    rc2 = guard_mod.main(["mark", "--root", str(tmp_path), "--session", SESSION])
    assert rc2 == 1  # unprocessed pending still blocks success
    assert not (tmp_path / guard_mod.MARKER_NAME).exists()

    _consume(pending)
    rc3 = guard_mod.main(["mark", "--root", str(tmp_path), "--session", SESSION])
    assert rc3 == 0
    marker = json.loads((tmp_path / guard_mod.MARKER_NAME).read_text(encoding="utf-8"))
    assert marker["session_date"] == SESSION
    assert marker["status"] == "success"


def test_marker_remains_valid_after_pending_is_renamed_to_processed(tmp_path):
    _seed(tmp_path)
    pending = _write_pending(tmp_path, SESSION)
    guard = ReviewSessionGuard(tmp_path)
    guard.begin(SESSION)
    _consume(pending)
    guard.mark_success(SESSION)
    guard.release()

    guard2 = ReviewSessionGuard(tmp_path)
    decision = guard2.begin(SESSION)
    guard2.release()
    assert decision.skip is True


def test_empty_pending_rename_is_fingerprint_stable(tmp_path):
    _seed(tmp_path)
    empty = _write_pending(tmp_path, SESSION, empty=True)
    guard = ReviewSessionGuard(tmp_path)
    assert guard.begin(SESSION).skip is False
    _consume(empty)
    guard.mark_success(SESSION)
    guard.release()

    guard2 = ReviewSessionGuard(tmp_path)
    decision = guard2.begin(SESSION)
    guard2.release()
    assert decision.skip is True


def test_history_compatibility_multiple_dates_empty_and_duplicate_events(tmp_path):
    _seed(tmp_path)
    old_processed = tmp_path / "us_stocks_pending_20261017.csv.processed"
    old_processed.write_text(
        "Date,Ticker,Tag,Name\n2026-10-17,AAA,Core_Dragon,AAA Inc\n", encoding="utf-8"
    )
    empty_processed = tmp_path / "us_stocks_pending_20261018.csv.processed"
    empty_processed.write_text("Date,Ticker,Tag,Name\n", encoding="utf-8")
    p19 = _write_pending(tmp_path, "2026-10-19", "AAA")       # duplicate event, older date
    p20 = _write_pending(tmp_path, SESSION, "BBB")
    before = sorted(p.name for p in tmp_path.glob("us_stocks_pending_*"))

    _complete(tmp_path, SESSION, [p19, p20])
    after = sorted(p.name for p in tmp_path.glob("us_stocks_pending_*"))
    assert len(before) == len(after)  # no history files deleted
    assert old_processed.exists() and empty_processed.exists()

    guard = ReviewSessionGuard(tmp_path)
    assert guard.begin(SESSION).skip is True
    guard.release()

    # A new empty pending file must still invalidate the success marker.
    _write_pending(tmp_path, "2026-10-21", empty=True)
    guard2 = ReviewSessionGuard(tmp_path)
    decision = guard2.begin(SESSION)
    guard2.release()
    assert decision.skip is False


def test_invalid_marker_is_treated_as_incomplete(tmp_path):
    _seed(tmp_path)
    _write_pending(tmp_path, SESSION)
    (tmp_path / guard_mod.MARKER_NAME).write_text("{not-json", encoding="utf-8")
    guard = ReviewSessionGuard(tmp_path)
    decision = guard.begin(SESSION)
    guard.release()
    assert decision.skip is False
