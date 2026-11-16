"""Dynamic Norgate 2-year trial window calculations.

This is a classification helper only. It does not imply that Norgate data was
downloaded or verified.
"""
from __future__ import annotations

from datetime import date


def _parse(value: str | None) -> date | None:
    if not value or value in {"NOT_VERIFIED", "NOT_STARTED"}:
        return None
    return date.fromisoformat(value)


def two_year_cutoff(trial_start_date: str) -> date:
    start = date.fromisoformat(trial_start_date)
    try:
        return start.replace(year=start.year - 2)
    except ValueError:  # 29 February
        return start.replace(year=start.year - 2, day=28)


def compute_trial_scope(last_trading_date: str | None, trial_start_date: str | None) -> str:
    """Return trial scope; no trial start means no candidate is validated."""
    if not trial_start_date or trial_start_date == "NOT_STARTED":
        return "TRIAL_NOT_STARTED"
    last = _parse(last_trading_date)
    if last is None:
        return "LAST_TRADING_DATE_UNKNOWN"
    return "CANDIDATE_IN_WINDOW" if last >= two_year_cutoff(trial_start_date) else "OUTSIDE_TRIAL_HISTORY"
