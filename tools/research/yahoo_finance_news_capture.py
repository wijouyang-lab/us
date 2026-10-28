"""Capture per-ticker Yahoo Finance headline RSS for prospective research only.

Yahoo Finance is an aggregator, not an official filing source. Publisher dates are
preserved as metadata; actual collector first-seen timestamps govern point-in-time
eligibility. Feed absence is not proof that no company event occurred.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
import re
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from tools.research.pit_event_records import normalize_event

_ALLOWED_HOST = "feeds.finance.yahoo.com"
_BASE_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline"
_TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.-]{0,14}$")
_DEFAULT_USER_AGENT = "wijouyang-lab/us research collector (contact: 288002660+wijouyang-lab@users.noreply.github.com)"


def build_yahoo_finance_rss_url(ticker: str) -> str:
    """Return the fixed Yahoo ticker-headline RSS URL for one normalized symbol."""
    symbol = str(ticker or "").strip().upper().replace("$", "")
    if not _TICKER_RE.fullmatch(symbol):
        raise ValueError(f"invalid ticker for Yahoo Finance RSS: {ticker!r}")
    url = f"{_BASE_URL}?{urlencode({'s': symbol, 'region': 'US', 'lang': 'en-US'})}"
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != _ALLOWED_HOST:
        raise ValueError("Yahoo Finance RSS URL failed host allowlist")
    return url


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":")[-1].lower()


def _child_text(node: ET.Element, names: set[str]) -> str:
    for child in list(node):
        if _local_name(child.tag) not in names:
            continue
        text = "".join(child.itertext()).strip()
        if text:
            return text
        href = str(child.attrib.get("href") or "").strip()
        if href:
            return href
    return ""


def _published_timestamp(raw: str) -> str | None:
    if not raw.strip():
        return None
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _utc_now(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("collector clock must return a timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class YahooFinanceRssCollector:
    """Fetch ticker-specific headline RSS feeds and keep per-ticker failure diagnostics."""

    def __init__(
        self,
        user_agent: str = "",
        *,
        min_request_interval_seconds: float = 0.2,
        opener: Callable[..., Any] | None = None,
        now: Callable[[], datetime] | None = None,
        sleep: Callable[[float], None] | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        if min_request_interval_seconds < 0.1:
            raise ValueError("minimum request interval must be at least 0.1 seconds")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.user_agent = str(user_agent or _DEFAULT_USER_AGENT).strip()
        self.min_request_interval_seconds = float(min_request_interval_seconds)
        self.opener = opener or urlopen
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.sleep = sleep or time.sleep
        self.timeout_seconds = float(timeout_seconds)

    def collect(self, tickers: list[str]) -> dict[str, Any]:
        if not isinstance(tickers, list):
            raise ValueError("tickers must be a list")
        symbols: list[str] = []
        for raw in tickers:
            symbol = str(raw or "").strip().upper().replace("$", "")
            if not _TICKER_RE.fullmatch(symbol):
                raise ValueError(f"invalid ticker for Yahoo Finance RSS: {raw!r}")
            if symbol not in symbols:
                symbols.append(symbol)

        all_events: list[dict[str, Any]] = []
        reports: list[dict[str, Any]] = []
        for index, ticker in enumerate(symbols):
            if index:
                self.sleep(self.min_request_interval_seconds)
            feed_url = build_yahoo_finance_rss_url(ticker)
            report = {
                "ticker": ticker,
                "feed_url": feed_url,
                "status": "fetch_or_parse_error",
                "item_count": 0,
                "event_count": 0,
                "duplicate_count_removed": 0,
                "malformed_item_count": 0,
                "missing_or_invalid_published_at_count": 0,
                "error_type": None,
                "error": None,
                "retrieved_at_utc": None,
                "source_payload_sha256": None,
            }
            response = None
            try:
                request = Request(
                    feed_url,
                    headers={
                        "User-Agent": self.user_agent,
                        "Accept": "application/rss+xml, application/xml, text/xml",
                    },
                )
                response = self.opener(request, timeout=self.timeout_seconds)
                payload = response.read()
                if isinstance(payload, str):
                    payload_bytes = payload.encode("utf-8")
                    payload_text = payload
                else:
                    payload_bytes = bytes(payload)
                    if len(payload_bytes) > 5_000_000:
                        raise ValueError("Yahoo Finance RSS response exceeds 5 MB safety limit")
                    payload_text = payload_bytes.decode("utf-8-sig")
                report["source_payload_sha256"] = sha256(payload_bytes).hexdigest()
                root = ET.fromstring(payload_text)
                items = [node for node in root.iter() if _local_name(node.tag) in {"item", "entry"}]
                retrieved_at = _utc_now(self.now())
                report["retrieved_at_utc"] = retrieved_at
                report["item_count"] = len(items)
                seen_items: set[str] = set()
                for node in items:
                    title = _child_text(node, {"title"})
                    link = _child_text(node, {"link"})
                    if not link:
                        # Atom-style feeds may provide link only as an href attribute.
                        link = next((
                            str(child.attrib.get("href") or "").strip()
                            for child in list(node)
                            if _local_name(child.tag) == "link" and child.attrib.get("href")
                        ), "")
                    guid = _child_text(node, {"guid", "id"})
                    pub_date_raw = _child_text(node, {"pubdate", "published", "updated", "date"})
                    publisher = _child_text(node, {"source"})
                    if not title:
                        report["malformed_item_count"] += 1
                        continue
                    stable_identity = guid or link or sha256(
                        f"{title}|{pub_date_raw}".encode("utf-8")
                    ).hexdigest()
                    if stable_identity in seen_items:
                        report["duplicate_count_removed"] += 1
                        continue
                    seen_items.add(stable_identity)
                    published_at = _published_timestamp(pub_date_raw)
                    if published_at is None:
                        report["missing_or_invalid_published_at_count"] += 1
                    event = normalize_event(
                        source="yahoo_finance_rss",
                        source_event_id=f"{ticker}|{stable_identity}",
                        event_type="company_news",
                        published_at_utc=published_at,
                        first_seen_at_utc=retrieved_at,
                        headline=title,
                        tickers=[ticker],
                        source_quality="aggregator",
                        raw_payload={
                            "ticker": ticker,
                            "title": title,
                            "link": link or None,
                            "guid": guid or None,
                            "pub_date_raw": pub_date_raw or None,
                            "publisher": publisher or None,
                        },
                    )
                    event.update({
                        "source_url": link or None,
                        "item_url": link or None,
                        "feed_url": feed_url,
                        "provider": "Yahoo Finance RSS",
                        "publisher_name": publisher or None,
                        "source_timestamp_kind": "rss_pubDate",
                        "source_timestamp_status": "parsed" if published_at else "missing_or_invalid",
                        "queried_ticker": ticker,
                        "ticker_mapping_method": "per_ticker_yahoo_rss_query",
                        "ticker_mapping_status": "unverified_query_scope",
                        "ticker_mapping_confidence": "unverified",
                        "research_only": True,
                    })
                    all_events.append(event)
                report["event_count"] = len(items) - report["malformed_item_count"] - report["duplicate_count_removed"]
                report["status"] = "ok"
            except HTTPError as exc:
                report["error_type"] = "HTTPError"
                report["error"] = f"HTTP {exc.code}"
            except (URLError, TimeoutError, OSError, UnicodeDecodeError, ET.ParseError, ValueError) as exc:
                report["error_type"] = type(exc).__name__
                report["error"] = str(exc)
            finally:
                if response is not None:
                    close = getattr(response, "close", None)
                    if callable(close):
                        close()
            reports.append(report)

        successful = sum(report["status"] == "ok" for report in reports)
        metadata = {
            "collector_version": "1.0",
            "source": "yahoo_finance_rss",
            "source_quality": "aggregator",
            "requested_tickers": symbols,
            "requested_ticker_count": len(symbols),
            "successful_ticker_count": successful,
            "failed_ticker_count": len(reports) - successful,
            "event_count": len(all_events),
            "ticker_reports": reports,
            "research_only": True,
            "production_scanner_modified": False,
            "limitations": [
                "Yahoo Finance RSS is an aggregator, not an official filing source.",
                "RSS pubDate is publisher metadata, not proof of the exact first-public instant.",
                "Only the collector's recorded first_seen_at_utc establishes when this system observed an item.",
                "A ticker-scoped query is not proof that each returned headline is about that company; ticker mapping is explicitly unverified until content review.",
                "The feed exposes a limited rolling window; absence does not prove no event occurred.",
                "The collector does not infer event sentiment or earnings labels from headline text.",
            ],
        }
        return {"events": all_events, "metadata": metadata}
