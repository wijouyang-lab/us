import json
from datetime import datetime, timezone

import pytest

from tools.research.official_event_rss_collector import (
    OFFICIAL_FEEDS,
    OfficialRssCollector,
    parse_official_feed,
)


class FakeResponse:
    def __init__(self, data, status=200):
        self.data = data if isinstance(data, bytes) else data.encode("utf-8")
        self.status = status

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def sample_bls_feed():
    return """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item>
        <title>CPI rose in August</title>
        <link>https://www.bls.gov/news.release/cpi.htm</link>
        <guid>bls-cpi-release-001</guid>
        <pubDate>Fri, 11 Sep 2026 08:30:00 -0400</pubDate>
        <description><![CDATA[Consumer prices increased <b>0.4%</b>.]]></description>
      </item>
      <item>
        <title>Item with no timestamp</title>
        <link>https://www.bls.gov/news.release/other.htm</link>
        <guid>bls-cpi-release-002</guid>
        <description>Example missing pubDate</description>
      </item>
    </channel></rss>
    """


def test_parse_bls_feed_normalizes_time_hash_and_missingness():
    result = parse_official_feed(
        sample_bls_feed(),
        feed_key="bls_cpi",
        first_seen_at_utc="2026-09-11T12:31:00Z",
    )
    assert result["item_count"] == 2
    assert result["event_count"] == 2
    first, second = result["events"]
    assert first["event_type"] == "macro_release"
    assert first["published_at_utc"] == "2026-09-11T12:30:00Z"
    assert first["first_seen_at_utc"] == "2026-09-11T12:31:00Z"
    assert first["availability_status"] == "available"
    assert first["market_scope"] == "market"
    assert first["source_url"] == "https://www.bls.gov/news.release/cpi.htm"
    assert len(first["content_hash"]) == 64
    assert first["headline"] == "CPI rose in August"
    assert second["published_at_utc"] is None
    assert second["availability_status"] == "timestamp_missing"
    assert result["timestamp_missing_count"] == 1


def test_federal_reserve_feed_classification_is_deterministic():
    body = """<rss><channel>
    <item><title>FOMC raises federal funds target range</title>
    <link>https://www.federalreserve.gov/newsevents/pressreleases/monetary20261001a.htm</link>
    <guid>fomc-1</guid><pubDate>Thu, 01 Oct 2026 14:00:00 GMT</pubDate></item>
    <item><title>Board announces enforcement action</title>
    <link>https://www.federalreserve.gov/newsevents/pressreleases/enforcement20261001a.htm</link>
    <guid>fed-2</guid><pubDate>Thu, 01 Oct 2026 14:10:00 GMT</pubDate></item>
    </channel></rss>"""
    result = parse_official_feed(
        body, feed_key="fed_all", first_seen_at_utc="2026-10-01T14:20:00Z",
    )
    assert [event["event_type"] for event in result["events"]] == ["central_bank", "policy"]
    assert all(event["market_scope"] == "market" for event in result["events"])
    assert result["events"][0]["published_at_utc"] == "2026-10-01T14:00:00Z"


def test_parse_rejects_unknown_feed_invalid_xml_and_naive_first_seen():
    with pytest.raises(ValueError, match="unsupported official feed"):
        parse_official_feed("<rss/>", feed_key="random", first_seen_at_utc="2026-10-01T14:20:00Z")
    with pytest.raises(ValueError, match="invalid RSS/XML"):
        parse_official_feed("<rss>", feed_key="bls_cpi", first_seen_at_utc="2026-10-01T14:20:00Z")
    with pytest.raises(ValueError, match="timezone-aware"):
        parse_official_feed("<rss/>", feed_key="bls_cpi", first_seen_at_utc="2026-10-01T14:20:00")


def test_collector_uses_only_allowlisted_feeds_and_reports_failures():
    sleeps = []
    url_seen = []

    def opener(request, timeout):
        url_seen.append(request.full_url)
        if request.full_url == OFFICIAL_FEEDS["bls_cpi"]["url"]:
            return FakeResponse(sample_bls_feed())
        if request.full_url == OFFICIAL_FEEDS["fed_all"]["url"]:
            return FakeResponse("<rss><channel>")
        return FakeResponse("<rss><channel/></rss>")

    fixed_now = datetime(2026, 9, 11, 12, 31, tzinfo=timezone.utc)
    collector = OfficialRssCollector(
        "Quant research test@example.com",
        opener=opener,
        sleep=sleeps.append,
        now=lambda: fixed_now,
    )
    result = collector.collect(["bls_cpi", "fed_all"])
    assert url_seen == [OFFICIAL_FEEDS["bls_cpi"]["url"], OFFICIAL_FEEDS["fed_all"]["url"]]
    assert sleeps == [0.2]
    assert result["metadata"]["event_count"] == 2
    assert result["metadata"]["feed_reports"][0]["status"] == "ok"
    assert result["metadata"]["feed_reports"][1]["status"] == "fetch_or_parse_error"
    assert result["metadata"]["research_only"] is True
    assert result["metadata"]["production_scanner_modified"] is False
    assert len(result["metadata"]["event_snapshot_sha256"]) == 64



def test_bea_release_feed_is_allowlisted_and_normalized_as_macro():
    body = """<rss><channel>
    <item><title>Personal Income and Outlays, August 2026</title>
    <link>https://www.bea.gov/news/2026/personal-income-and-outlays-august-2026</link>
    <guid>bea-pce-2026-08</guid><pubDate>Wed, 30 Sep 2026 08:30:00 -0400</pubDate>
    <description>Personal income and outlays release.</description></item>
    </channel></rss>"""
    result = parse_official_feed(
        body, feed_key="bea_releases", first_seen_at_utc="2026-09-30T12:31:00Z",
    )
    event = result["events"][0]
    assert event["event_type"] == "macro_release"
    assert event["source"] == "bea_news_release_rss"
    assert event["feed_key"] == "bea_releases"
    assert event["published_at_utc"] == "2026-09-30T12:30:00Z"
    assert event["source_url"] == "https://www.bea.gov/news/2026/personal-income-and-outlays-august-2026"
    assert event["market_scope"] == "market"



def test_bea_feed_fetch_uses_official_allowlisted_host():
    seen = []
    body = """<rss><channel>
    <item><title>GDP release</title><link>https://www.bea.gov/news/current-releases</link>
    <guid>bea-gdp-1</guid><pubDate>Thu, 29 Oct 2026 08:30:00 -0400</pubDate></item>
    </channel></rss>"""

    def opener(request, timeout):
        seen.append(request.full_url)
        return FakeResponse(body)

    collector = OfficialRssCollector(
        "Quant research test@example.com",
        opener=opener,
        sleep=lambda _: None,
        now=lambda: datetime(2026, 10, 29, 12, 31, tzinfo=timezone.utc),
    )
    result = collector.collect(["bea_releases"])
    assert seen == ["https://apps.bea.gov/rss/rss.xml"]
    assert result["metadata"]["feed_reports"][0]["status"] == "ok"
    assert result["metadata"]["event_count"] == 1

def test_collector_requires_contact_user_agent_and_recognized_feed_keys():
    with pytest.raises(ValueError, match="contact email"):
        OfficialRssCollector("no email")
    collector = OfficialRssCollector(
        "Quant research test@example.com",
        opener=lambda *args, **kwargs: pytest.fail("should not perform a request"),
        sleep=lambda _: None,
    )
    with pytest.raises(ValueError, match="unsupported official feed"):
        collector.collect(["custom_url"])


def test_federal_reserve_speeches_feed_is_classified_as_central_bank():
    body = """<rss><channel>
    <item><title>Chair gives remarks on the economic outlook</title>
    <link>https://www.federalreserve.gov/newsevents/speech/chair20261001a.htm</link>
    <guid>fed-speech-1</guid><pubDate>Thu, 01 Oct 2026 14:00:00 GMT</pubDate></item>
    </channel></rss>"""
    result = parse_official_feed(
        body, feed_key="fed_speeches", first_seen_at_utc="2026-10-01T14:20:00Z",
    )
    assert result["events"][0]["event_type"] == "central_bank"
    assert result["events"][0]["feed_key"] == "fed_speeches"


def test_feed_sort_places_missing_source_timestamps_last():
    result = parse_official_feed(
        sample_bls_feed(),
        feed_key="bls_cpi",
        first_seen_at_utc="2026-09-11T12:31:00Z",
    )
    assert result["events"][0]["published_at_utc"] == "2026-09-11T12:30:00Z"
    assert result["events"][1]["published_at_utc"] is None


@pytest.mark.parametrize("feed_key", ["treasury_auction_announcements", "treasury_auction_results"])
def test_treasury_feeds_are_allowlisted_and_normalized(feed_key):
    cfg = OFFICIAL_FEEDS[feed_key]
    assert cfg["url"].startswith("https://www.treasurydirect.gov/")
    body = "<rss><channel><item><title>Auction event</title><link>https://www.treasurydirect.gov/news</link><guid>auction-test-1</guid><pubDate>Thu, 29 Oct 2026 08:30:00 -0400</pubDate></item></channel></rss>"
    result = parse_official_feed(body, feed_key=feed_key, first_seen_at_utc="2026-10-29T12:31:00Z")
    assert result["events"][0]["source"] == cfg["source"]
    assert result["events"][0]["event_type"] == "macro_release"
    assert result["events"][0]["market_scope"] == "market"


@pytest.mark.parametrize("feed_key", ["treasury_auction_announcements", "treasury_auction_results"])
def test_treasury_feed_fetch_uses_configured_official_url(feed_key):
    seen = []
    body = "<rss><channel><item><title>Auction event</title><link>https://www.treasurydirect.gov/news</link><guid>auction-fetch-test</guid><pubDate>Thu, 29 Oct 2026 08:30:00 -0400</pubDate></item></channel></rss>"
    def opener(request, timeout):
        seen.append(request.full_url)
        return FakeResponse(body)
    collector = OfficialRssCollector("Quant research test@example.com", opener=opener, sleep=lambda _: None, now=lambda: datetime(2026, 10, 29, 12, 31, tzinfo=timezone.utc))
    result = collector.collect([feed_key])
    assert seen == [OFFICIAL_FEEDS[feed_key]["url"]]
    assert result["metadata"]["feed_reports"][0]["status"] == "ok"
    assert result["metadata"]["event_count"] == 1
