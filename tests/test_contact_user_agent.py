# -*- coding: utf-8 -*-
"""Contact User-Agent validation tests; no real identity or network."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import contact_user_agent as ua  # noqa: E402
from official_event_rss_collector import ContactUserAgentRequired, OfficialRssCollector  # noqa: E402
from sec_event_collector import SecEventCollector  # noqa: E402


def test_missing_and_multiline_are_rejected():
    assert ua.load_user_agent({}, ("OFFICIAL_FEED_USER_AGENT",)) is None
    with pytest.raises(ValueError):
        ua.validate_user_agent("")
    with pytest.raises(ValueError):
        ua.validate_user_agent("app\nInjected: x")
    with pytest.raises(ValueError):
        ua.validate_user_agent(None, require_email=True)


def test_placeholder_identity_is_rejected():
    for value in ("app test@example.com", "app user@example.org", "app contact@test.com"):
        assert ua.has_contact_email(value) is False
        with pytest.raises(ValueError):
            ua.validate_user_agent(value, require_email=True)


def test_valid_contact_email_is_accepted_and_redacted():
    agent = "wj-research/1.0 (tester@quantlab.dev)"
    assert ua.has_contact_email(agent)
    assert ua.validate_user_agent(agent, require_email=True) == agent
    assert "tester@" not in ua.redact_user_agent(agent)
    assert "***@quantlab.dev" in ua.redact_user_agent(agent)


def test_env_loading_uses_first_nonempty_value():
    env = {"A": "", "B": "wj-research tester@quantlab.dev"}
    assert ua.load_user_agent(env, ("A", "B"), require_email=True).startswith("wj-research")


def test_collectors_reject_placeholder_contact():
    with pytest.raises(ValueError):
        OfficialRssCollector("app test@example.com")
    with pytest.raises(ValueError):
        SecEventCollector("app test@example.com")


def test_bls_without_contact_is_skipped():
    collector = OfficialRssCollector()
    with pytest.raises(ContactUserAgentRequired):
        collector._fetch("bls_cpi")
