from datetime import datetime, timezone
from io import BytesIO
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

from tools.research.yahoo_finance_news_capture import (
    YahooFinanceRssCollector,
    build_yahoo_finance_rss_url,
)

NOW = datetime(2026, 10, 26, 17, 0, tzinfo=timezone.utc)
RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Example Corp reports quarterly results</title>
    <link>https://finance.yahoo.com/news/example-results.html</link>
    <guid isPermaLink="false">story-001</guid>
    <pubDate>Mon, 26 Oct 2026 16:30:00 +0000</pubDate>
    <source url="https://www.reuters.com/">Reuters</source>
  </item>
  <item>
    <title>Example Corp reports quarterly results</title>
    <link>https://finance.yahoo.com/news/example-results.html</link>
    <guid isPermaLink="false">story-001</guid>
    <pubDate>Mon, 26 Oct 2026 16:30:00 +0000</pubDate>
    <source url="https://www.reuters.com/">Reuters</source>
  </item>
  <item>
    <title>Example Corp issues another statement</title>
    <link>https://finance.yahoo.com/news/example-statement.html</link>
    <guid isPermaLink="false">story-002</guid>
    <source url="https://www.reuters.com/">Reuters</source>
  </item>
</channel></rss>
"""


class Response(BytesIO):
    pass


def test_yahoo_feed_url_is_fixed_host_and_symbol_scoped():
    url = build_yahoo_finance_rss_url("aapl")
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "feeds.finance.yahoo.com"
    assert parse_qs(parsed.query) == {"s": ["AAPL"], "region": ["US"], "lang": ["en-US"]}


def test_yahoo_collector_records_first_seen_and_rss_timestamp_and_deduplicates():
    seen = {}

    def opener(request, timeout):
        seen["url"] = request.full_url
        seen["user_agent"] = request.get_header("User-agent")
        seen["timeout"] = timeout
        return Response(RSS)

    collector = YahooFinanceRssCollector(
        "research collector (contact: analyst@example.com)",
        opener=opener,
        now=lambda: NOW,
        sleep=lambda _seconds: None,
    )
    result = collector.collect(["AAPL", "AAPL"])

    assert len(result["events"]) == 2
    assert result["metadata"]["requested_tickers"] == ["AAPL"]
    assert result["metadata"]["successful_ticker_count"] == 1
    report = result["metadata"]["ticker_reports"][0]
    assert report["status"] == "ok"
    assert report["item_count"] == 3
    assert report["duplicate_count_removed"] == 1
    assert report["missing_or_invalid_published_at_count"] == 1
    first = result["events"][0]
    assert first["source"] == "yahoo_finance_rss"
    assert first["source_quality"] == "aggregator"
    assert first["event_type"] == "company_news"
    assert first["tickers"] == ["AAPL"]
    assert first["published_at_utc"] == "2026-10-26T16:30:00Z"
    assert first["first_seen_at_utc"] == "2026-10-26T17:00:00Z"
    assert first["source_url"] == "https://finance.yahoo.com/news/example-results.html"
    assert first["publisher_name"] == "Reuters"
    second = next(event for event in result["events"] if "another statement" in event["headline"])
    assert second["published_at_utc"] is None
    assert second["availability_status"] == "timestamp_missing"
    assert seen["user_agent"]
    assert seen["timeout"] > 0


def test_yahoo_collector_records_http_403_per_ticker_and_continues():
    calls = []

    def opener(request, timeout):
        calls.append(request.full_url)
        if "AAPL" in request.full_url:
            raise HTTPError(request.full_url, 403, "Forbidden", {}, None)
        return Response(RSS)

    result = YahooFinanceRssCollector(
        opener=opener,
        now=lambda: NOW,
        sleep=lambda _seconds: None,
    ).collect(["AAPL", "MSFT"])

    assert len(calls) == 2
    assert result["metadata"]["successful_ticker_count"] == 1
    assert result["metadata"]["failed_ticker_count"] == 1
    assert result["metadata"]["ticker_reports"][0]["error"] == "HTTP 403"
    assert result["metadata"]["ticker_reports"][1]["status"] == "ok"
    assert all(event["tickers"] == ["MSFT"] for event in result["events"])


def test_yahoo_collector_rejects_invalid_symbols_without_network():
    result = None
    try:
        YahooFinanceRssCollector().collect(["AAPL&admin=true"])
    except ValueError as exc:
        assert "invalid ticker" in str(exc)
    else:
        raise AssertionError("invalid ticker should be rejected")
