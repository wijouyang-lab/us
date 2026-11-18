import pytest

from tools.automation.publisher import _valid_sha, _valid_url, transition_ok


@pytest.mark.parametrize("local,remote", [
    ("PUBLISHING", "PUBLISHING"),
    ("PUBLISHING", "REVIEW_PENDING"),
    ("PUBLISHING", "PASS"),
    ("REVIEW_PENDING", "PASS"),
    ("REVIEW_PENDING", "REVIEW_PENDING"),
    ("BLOCKED", "PUBLISHING"),
])
def test_allowed_transitions(local, remote):
    assert transition_ok(local, remote, "BUSINESS_PUSH_FAILED")


@pytest.mark.parametrize("local,remote", [
    ("PASS", "PUBLISHING"),
    ("REVIEW_PENDING", "PUBLISHING"),
    ("FAIL", "PUBLISHING"),
    ("FAIL", "RUNNING"),
    ("UNKNOWN", "PUBLISHING"),
])
def test_rejected_transitions(local, remote):
    assert transition_ok(local, remote) is False


def test_blocked_requires_recoverable_reason():
    assert transition_ok("BLOCKED", "PUBLISHING", "READY_PR_BLOCKED") is True
    assert transition_ok("BLOCKED", "PUBLISHING", "UNKNOWN_REASON") is False


def test_sha_and_url_formats():
    assert _valid_sha("a" * 40)
    assert not _valid_sha("a" * 39)
    assert not _valid_sha("z" * 40)
    assert _valid_url("https://github.com/x/y/pull/1")
    assert not _valid_url("not-a-url")
