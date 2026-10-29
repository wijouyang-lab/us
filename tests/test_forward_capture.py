# -*- coding: utf-8 -*-
"""Tests for the manual forward-capture whitelist."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import forward_capture as f  # noqa: E402


def test_fed_press_urls_allowed():
    assert f.allowed("https://www.federalreserve.gov/newsevents/pressreleases/monetary20250319a.htm")
    assert f.allowed("https://www.federalreserve.gov/newsevents/press/monetary/20100127a.htm?utm=1")


def test_other_hosts_and_paths_rejected():
    assert not f.allowed("https://example.com/newsevents/pressreleases/monetary20250319a.htm")
    assert not f.allowed("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm")
