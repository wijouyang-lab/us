#!/usr/bin/env python3
"""Parse official Federal Reserve press-release pages for release timestamps.

The result is retrospective: the page publication time is not a historical
first-seen observation.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from bs4 import BeautifulSoup

_DATE_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2}),\s+(\d{4})"
)
_TIME_RE = re.compile(
    r"For release at\s+(\d{1,2}):(\d{2})\s*(a\.?m\.?|p\.?m\.?)\s*(EDT|EST)",
    re.IGNORECASE,
)
_MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}


def parse_release_page(html: str, source_url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    time_node = soup.select_one("p.article__time")
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    date_match = _DATE_RE.search(time_node.get_text(" ", strip=True)) if time_node else _DATE_RE.search(text)
    time_match = _TIME_RE.search(text)
    result = {
        "source_url": source_url,
        "published_at_utc": None,
        "published_date": None,
        "release_time_local": None,
        "timezone": None,
        "timestamp_precision": "date_only",
        "parse_status": "date_only",
        "parse_reason": None,
    }
    if not date_match:
        result["parse_status"] = "failed"
        result["parse_reason"] = "no_page_date"
        return result
    year, month, day = int(date_match.group(3)), _MONTHS[date_match.group(1)], int(date_match.group(2))
    result["published_date"] = f"{year:04d}-{month:02d}-{day:02d}"
    if not time_match:
        result["parse_reason"] = "no_release_time"
        return result
    hour, minute = int(time_match.group(1)), int(time_match.group(2))
    ampm = time_match.group(3).replace(".", "").lower()
    zone = time_match.group(4).upper()
    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    offset = timedelta(hours=-4 if zone == "EDT" else -5)
    try:
        local = datetime(year, month, day, hour, minute, tzinfo=timezone(offset))
    except ValueError:
        result["parse_status"] = "failed"
        result["parse_reason"] = "invalid_date_time"
        return result
    result.update({
        "published_at_utc": local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "release_time_local": f"{hour:02d}:{minute:02d}",
        "timezone": zone,
        "timestamp_precision": "minute",
        "parse_status": "exact",
        "parse_reason": None,
    })
    return result
