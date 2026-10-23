"""Free official BLS, BEA, Federal Reserve, and TreasuryDirect RSS capture for research-only event observation.

The collector uses a built-in allowlist of official feeds and local parsing tests.
Publisher-supplied RSS dates are preserved as source timestamps, not treated as
proof of the exact public-availability instant. The collector's real first-seen
timestamp is recorded separately. No production scanner or scheduled workflow
is modified.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from tools.research.pit_event_records import normalize_event

OFFICIAL_FEEDS: dict[str, dict[str, str]] = {
    "bls_cpi": {
        "url": "https://www.bls.gov/feed/cpi.rss",
        "source": "bls_cpi_rss",
        "event_type": "macro_release",
        "source_quality": "official",
    },
    "bls_employment": {
        "url": "https://www.bls.gov/feed/empsit.rss",
        "source": "bls_employment_situation_rss",
        "event_type": "macro_release",
        "source_quality": "official",
    },
    "bea_releases": {
        "url": "https://apps.bea.gov/rss/rss.xml",
        "source": "bea_news_release_rss",
        "event_type": "macro_release",
        "source_quality": "official",
    },
    "treasury_auction_announcements": {
        "url": "https://www.treasurydirect.gov/TA_WS/securities/announced/rss",
        "source": "treasury_auction_announcements_rss",
        "event_type": "macro_release",
        "source_quality": "official",
    },
    "treasury_auction_results": {
        "url": "https://www.treasurydirect.gov/TA_WS/securities/auctioned/rss",
        "source": "treasury_auction_results_rss",
        "event_type": "macro_release",
        "source_quality": "official",
    },
    "fed_all": {
        "url": "https://www.federalreserve.gov/feeds/press_all.xml",
        "source": "federal_reserve_press_rss",
        "event_type": "policy",
        "source_quality": "official",
    },
    "fed_speeches": {
        "url": "https://www.federalreserve.gov/feeds/speeches_and_testimony.xml",
        "source": "federal_reserve_speeches_rss",
        "event_type": "central_bank",
        "source_quality": "official",
    },
}
_ALLOWED_HOSTS = {"www.bls.gov", "www.federalreserve.gov", "apps.bea.gov", "www.treasurydirect.gov"}
_CENTRAL_BANK_TERMS = (
    "fomc",
    "monetary policy",
    "federal funds",
    "interest rate",
    "policy rate",
    "federal open market committee",
    "longer-run goals",
    "reserve balances",
)


def _aware_utc(value: str | datetime) -> str:
    parsed = value if isinstance(value, datetime) else _parse_datetime(value)
    if parsed is None or parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("first_seen_at_utc must be timezone-aware")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is not None and parsed.utcoffset() is not None:
            return parsed
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":")[-1].lower()


def _direct_child_text(node: ET.Element, names: set[str]) -> str:
    for child in list(node):
        if _local_name(child.tag) in names:
            text = "".join(child.itertext()).strip()
            if text:
                return text
    return ""


class _StripHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def _plain_text(value: str) -> str:
    parser = _StripHTML()
    try:
        parser.feed(value)
        parser.close()
        stripped = " ".join(parser.parts)
    except Exception:
        stripped = value
    return re.sub(r"\s+", " ", stripped).strip()


def _feed_event_type(feed_key: str, title: str, description: str) -> str:
    configured = OFFICIAL_FEEDS[feed_key]["event_type"]
    if feed_key == "fed_speeches":
        return "central_bank"
    if feed_key != "fed_all":
        return configured
    text = f"{title} {description}".lower()
    return "central_bank" if any(term in text for term in _CENTRAL_BANK_TERMS) else "policy"


_OFFICIAL_ITEM_HOSTS = {
    "www.bls.gov",
    "www.bea.gov",
    "apps.bea.gov",
    "www.federalreserve.gov",
    "www.treasurydirect.gov",
    "home.treasury.gov",
}


def _normalize_item_url(link: str | None, feed_url: str) -> str:
    """Canonicalize relative and scheme-less links from known official feeds."""
    raw = str(link or "").strip()
    if not raw:
        return feed_url
    if raw.startswith("//"):
        return "https:" + raw
    if raw.startswith("https://"):
        return raw
    if raw.startswith("http://"):
        # Preserve explicitly insecure source URLs so the readiness audit can flag them.
        return raw
    candidate = raw.lstrip("/")
    host = candidate.split("/", 1)[0].lower()
    if host in _OFFICIAL_ITEM_HOSTS:
        return "https://" + candidate
    if raw.startswith("/"):
        return urljoin(feed_url, raw)
    return urljoin(feed_url, raw)


def parse_official_feed(
    payload: bytes | str,
    *,
    feed_key: str,
    first_seen_at_utc: str | datetime,
) -> dict[str, Any]:
    """Parse caller-supplied RSS/Atom XML; this function never performs network I/O."""
    if feed_key not in OFFICIAL_FEEDS:
        raise ValueError(f"unsupported official feed: {feed_key}")
    first_seen = _aware_utc(first_seen_at_utc)
    try:
        root = ET.fromstring(payload)
    except (ET.ParseError, TypeError, ValueError) as exc:
        raise ValueError("invalid RSS/XML payload") from exc

    items = [
        node for node in root.iter()
        if _local_name(node.tag) in {"item", "entry"}
    ]
    source_info = OFFICIAL_FEEDS[feed_key]
    records: list[dict[str, Any]] = []
    duplicate_ids = 0
    seen_ids: set[str] = set()
    for item in items:
        title = _plain_text(_direct_child_text(item, {"title"}))
        description = _plain_text(_direct_child_text(
            item, {"description", "summary", "content", "encoded"}
        ))
        link = _direct_child_text(item, {"link"})
        if not link:
            for child in list(item):
                if _local_name(child.tag) == "link":
                    link = str(child.attrib.get("href") or "").strip()
                    if link:
                        break
        guid = _direct_child_text(item, {"guid", "id"})
        published_raw = _direct_child_text(item, {"pubdate", "published", "updated", "date"})
        published_dt = _parse_datetime(published_raw)
        published = (
            published_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            if published_dt is not None else None
        )
        identity_source = guid or link or f"{title}|{published_raw}"
        source_event_id = identity_source.strip()
        if not source_event_id or not title:
            continue
        identity = sha256(f"{source_info['source']}|{source_event_id}".encode("utf-8")).hexdigest()
        if identity in seen_ids:
            duplicate_ids += 1
            continue
        seen_ids.add(identity)
        event_type = _feed_event_type(feed_key, title, description)
        record = normalize_event(
            source=source_info["source"],
            source_event_id=source_event_id,
            event_type=event_type,
            published_at_utc=published,
            first_seen_at_utc=first_seen,
            headline=title,
            sectors=[],
            source_quality=source_info["source_quality"],
            raw_payload={
                "feed_key": feed_key,
                "feed_url": source_info["url"],
                "guid": guid or None,
                "link": link or None,
                "title": title,
                "description": description or None,
                "pubDate_raw": published_raw or None,
            },
        )
        record["source_url"] = _normalize_item_url(link, source_info["url"])
        record["feed_key"] = feed_key
        # These allowlisted feeds publish market-wide macro/policy information.
        # Explicit scope lets the point-in-time feature builder include them for
        # each ticker; unrelated company news still requires an explicit ticker.
        record["market_scope"] = "market"
        record["source_timestamp_kind"] = "rss_published_at" if published else None
        record["source_timestamp_status"] = "parsed" if published else "timestamp_missing"
        records.append(record)

    records.sort(key=lambda row: (
        row.get("published_at_utc") is None,
        str(row.get("published_at_utc") or ""),
        str(row.get("event_id") or ""),
    ))
    return {
        "feed_key": feed_key,
        "feed_url": source_info["url"],
        "item_count": len(items),
        "event_count": len(records),
        "duplicate_id_count": duplicate_ids,
        "timestamp_missing_count": sum(
            row.get("availability_status") == "timestamp_missing" for row in records
        ),
        "events": records,
        "first_seen_at_utc": first_seen,
    }


class OfficialRssCollector:
    """Paced client limited to preconfigured official BLS, BEA, Fed, and TreasuryDirect feeds."""

    def __init__(
        self,
        user_agent: str,
        *,
        timeout_seconds: float = 20.0,
        min_request_interval_seconds: float = 0.2,
        opener: Callable[..., Any] | None = None,
        sleep: Callable[[float], None] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(user_agent, str) or not user_agent.strip():
            raise ValueError("User-Agent must identify the research application")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if min_request_interval_seconds < 0.1:
            raise ValueError("request interval must be at least 0.1 seconds")
        self.user_agent = user_agent.strip()
        self.timeout_seconds = timeout_seconds
        self.min_request_interval_seconds = min_request_interval_seconds
        self.opener = opener or urlopen
        self.sleep = sleep or time.sleep
        self.now = now or (lambda: datetime.now(timezone.utc))
        self._has_requested = False

    def _fetch(self, feed_key: str) -> tuple[bytes, str]:
        if feed_key not in OFFICIAL_FEEDS:
            raise ValueError(f"unsupported official feed: {feed_key}")
        url = OFFICIAL_FEEDS[feed_key]["url"]
        parsed_url = urlparse(url)
        if parsed_url.scheme != "https" or parsed_url.hostname not in _ALLOWED_HOSTS:
            raise ValueError("official feed URL failed host allowlist")
        if self._has_requested:
            self.sleep(self.min_request_interval_seconds)
        self._has_requested = True
        request = Request(url, headers={
            "User-Agent": self.user_agent,
            "Accept": "application/rss+xml, application/atom+xml, text/xml;q=0.9",
        })
        try:
            with self.opener(request, timeout=self.timeout_seconds) as response:
                status = int(getattr(response, "status", 200))
                if status < 200 or status >= 300:
                    raise RuntimeError(f"official RSS returned HTTP {status}")
                payload = response.read()
                observed_at = _aware_utc(self.now())
                return payload, observed_at
        except RuntimeError:
            raise
        except Exception as exc:
            status_code = getattr(exc, "code", None)
            cause = getattr(exc, "__cause__", None)
            if status_code is None:
                status_code = getattr(cause, "code", None)
            detail = f" HTTP {status_code}" if status_code is not None else ""
            raise RuntimeError(
                f"failed to fetch official feed {feed_key}: {type(exc).__name__}{detail}"
            ) from exc

    def collect(self, feed_keys: list[str]) -> dict[str, Any]:
        """Capture selected feeds without losing per-feed failures."""
        requested = list(dict.fromkeys(feed_keys))
        if not requested:
            raise ValueError("at least one feed key is required")
        unknown = [key for key in requested if key not in OFFICIAL_FEEDS]
        if unknown:
            raise ValueError(f"unsupported official feed(s): {', '.join(unknown)}")

        collection_started = _aware_utc(self.now())
        all_events: list[dict[str, Any]] = []
        feed_reports: list[dict[str, Any]] = []
        for key in requested:
            try:
                payload, first_seen = self._fetch(key)
                result = parse_official_feed(
                    payload,
                    feed_key=key,
                    first_seen_at_utc=first_seen,
                )
                raw_hash = sha256(payload).hexdigest()
                all_events.extend(result["events"])
                feed_reports.append({
                    "feed_key": key,
                    "feed_url": OFFICIAL_FEEDS[key]["url"],
                    "status": "ok",
                    "first_seen_at_utc": first_seen,
                    "source_payload_sha256": raw_hash,
                    "item_count": result["item_count"],
                    "event_count": result["event_count"],
                    "duplicate_id_count": result["duplicate_id_count"],
                    "timestamp_missing_count": result["timestamp_missing_count"],
                })
            except Exception as exc:
                feed_reports.append({
                    "feed_key": key,
                    "feed_url": OFFICIAL_FEEDS[key]["url"],
                    "status": "fetch_or_parse_error",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "event_count": 0,
                })

        all_events.sort(key=lambda row: (
            row.get("published_at_utc") is None,
            str(row.get("published_at_utc") or ""),
            str(row.get("event_id") or ""),
        ))
        snapshot_json = json.dumps(
            all_events, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        )
        metadata = {
            "collector_version": "1.0",
            "collection_started_at_utc": collection_started,
            "collection_completed_at_utc": _aware_utc(self.now()),
            "requested_feed_keys": requested,
            "event_count": len(all_events),
            "event_snapshot_sha256": sha256(snapshot_json.encode("utf-8")).hexdigest(),
            "feed_reports": feed_reports,
            "limitations": [
                "RSS pubDate is provider metadata and is not proof of the exact instant the item first became publicly visible.",
                "first_seen_at_utc is the collector's actual observation timestamp and must be used for strict point-in-time replay.",
                "RSS feeds expose a limited recent window; feed absence is not proof that no event occurred.",
                "This collector does not provide historical consensus values; it cannot calculate valid historical macro surprises by itself.",
            ],
            "research_only": True,
            "production_scanner_modified": False,
        }
        return {"metadata": metadata, "events": all_events}


def _load_feed_keys(raw: str) -> list[str]:
    keys = [key.strip() for key in raw.split(",") if key.strip()]
    if not keys:
        raise ValueError("provide at least one feed key")
    unknown = [key for key in keys if key not in OFFICIAL_FEEDS]
    if unknown:
        raise ValueError(f"unsupported feed key(s): {', '.join(unknown)}")
    return list(dict.fromkeys(keys))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feeds", default="bls_cpi,bls_employment,bea_releases,fed_all,fed_speeches,treasury_auction_announcements,treasury_auction_results")
    parser.add_argument("--output", required=True, help="Path for normalized event JSON array")
    parser.add_argument("--metadata-output", help="Path for collection metadata JSON")
    parser.add_argument("--user-agent", default=os.environ.get("OFFICIAL_FEED_USER_AGENT", ""))
    parser.add_argument("--min-request-interval-seconds", type=float, default=0.2)
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing existing output files")
    args = parser.parse_args(argv)

    try:
        keys = _load_feed_keys(args.feeds)
        output = Path(args.output)
        metadata_output = Path(args.metadata_output) if args.metadata_output else output.with_suffix(".metadata.json")
        if output.resolve() == metadata_output.resolve():
            raise ValueError("event output and metadata output must be different files")
        existing = [str(path) for path in (output, metadata_output) if path.exists()]
        if existing and not args.overwrite:
            raise ValueError(
                f"refusing to overwrite existing snapshot output(s): {', '.join(existing)}; "
                "choose new output paths or pass --overwrite"
            )
        collector = OfficialRssCollector(
            args.user_agent,
            min_request_interval_seconds=args.min_request_interval_seconds,
        )
        result = collector.collect(keys)
        output.write_text(
            json.dumps(result["events"], sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        metadata_output.write_text(
            json.dumps(result["metadata"], sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    print(f"Saved {len(result['events'])} events to {output}")
    print(f"Saved feed metadata to {metadata_output}")
    if all(report["status"] != "ok" for report in result["metadata"]["feed_reports"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
