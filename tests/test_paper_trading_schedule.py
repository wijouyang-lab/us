from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from paper_trading_schedule import should_run_eod


def test_dst_cron_only_one_schedule_is_allowed():
    # July: 20:30 UTC is 16:30 EDT; 21:30 UTC is 17:30 EDT.
    assert should_run_eod(datetime(2026, 7, 20, 20, 30, tzinfo=timezone.utc))
    assert not should_run_eod(datetime(2026, 7, 20, 21, 30, tzinfo=timezone.utc))


def test_standard_time_cron_only_one_schedule_is_allowed():
    # January: 20:30 UTC is 15:30 EST; 21:30 UTC is 16:30 EST.
    assert not should_run_eod(datetime(2026, 1, 20, 20, 30, tzinfo=timezone.utc))
    assert should_run_eod(datetime(2026, 1, 20, 21, 30, tzinfo=timezone.utc))


def test_weekends_never_run_eod():
    # Saturday 16:30 in New York.
    assert not should_run_eod(datetime(2026, 7, 25, 20, 30, tzinfo=timezone.utc))


def test_gate_uses_new_york_local_hour():
    assert not should_run_eod(datetime(2026, 7, 20, 19, 59, tzinfo=timezone.utc))  # 15:59 EDT
    assert should_run_eod(datetime(2026, 7, 20, 20, 59, tzinfo=timezone.utc))  # 16:59 EDT
    assert not should_run_eod(datetime(2026, 7, 20, 21, 0, tzinfo=timezone.utc))  # 17:00 EDT


if __name__ == "__main__":
    tests = [
        test_dst_cron_only_one_schedule_is_allowed,
        test_standard_time_cron_only_one_schedule_is_allowed,
        test_weekends_never_run_eod,
        test_gate_uses_new_york_local_hour,
    ]
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
    print(f"Result: {len(tests)}/{len(tests)} passed")
