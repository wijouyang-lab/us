# -*- coding: utf-8 -*-
"""Tests for Fed press-page release-time parsing; no network."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import fed_historical_press as fed  # noqa: E402

HTML = """<html><body>
<p class="article__time">October 16, 2026</p>
<p>For release at 11:00 a.m. EDT</p>
</body></html>"""


def test_exact_edt_release_time():
    out = fed.parse_release_page(HTML, "https://example.test/release")
    assert out["published_date"] == "2026-10-16"
    assert out["published_at_utc"] == "2026-10-16T15:00:00Z"
    assert out["timezone"] == "EDT"
    assert out["timestamp_precision"] == "minute"
    assert out["parse_status"] == "exact"


def test_est_conversion_and_noon_midnight():
    html = HTML.replace("October 16, 2026", "January 16, 2026").replace("11:00 a.m. EDT", "12:00 p.m. EST")
    out = fed.parse_release_page(html, "u")
    assert out["published_at_utc"] == "2026-01-16T17:00:00Z"
    html = HTML.replace("11:00 a.m. EDT", "12:00 a.m. EST")
    out = fed.parse_release_page(html, "u")
    assert out["published_at_utc"] == "2026-10-16T05:00:00Z"


def test_missing_time_stays_date_only():
    out = fed.parse_release_page(HTML.replace("For release at 11:00 a.m. EDT", "For release"), "u")
    assert out["timestamp_precision"] == "date_only"
    assert out["published_at_utc"] is None
    assert out["parse_reason"] == "no_release_time"


def test_missing_date_fails_closed():
    out = fed.parse_release_page("<p>No date</p>", "u")
    assert out["parse_status"] == "failed"
    assert out["published_at_utc"] is None


def test_invalid_time_fails_closed():
    out = fed.parse_release_page(HTML.replace("11:00", "25:00"), "u")
    assert out["parse_status"] == "failed"
