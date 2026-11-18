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
    assert not _valid_url("https://")
    assert not _valid_url("https://?x")
    assert not _valid_url("")
    assert not _valid_url("https://-bad.com")
    assert not _valid_url("https://bad-.com")
    assert not _valid_url("https://bad..com")
    assert not _valid_url("https://example.com:99999")
    assert not _valid_url("https://example.com:bad")
    assert _valid_url("http://example.com:8080/x")


def test_complete_state_transition_matrix():
    statuses = ["QUEUED", "RUNNING", "PUBLISHING", "NEEDS_REVISION", "BLOCKED", "REVIEW_PENDING", "PASS", "FAIL"]
    allowed = {
        ("QUEUED", "QUEUED"), ("QUEUED", "RUNNING"), ("QUEUED", "BLOCKED"),
        ("RUNNING", "RUNNING"), ("RUNNING", "PUBLISHING"), ("RUNNING", "BLOCKED"), ("RUNNING", "FAIL"),
        ("PUBLISHING", "PUBLISHING"), ("PUBLISHING", "REVIEW_PENDING"), ("PUBLISHING", "PASS"), ("PUBLISHING", "BLOCKED"), ("PUBLISHING", "FAIL"), ("PUBLISHING", "NEEDS_REVISION"),
        ("NEEDS_REVISION", "NEEDS_REVISION"), ("NEEDS_REVISION", "PUBLISHING"),
        ("BLOCKED", "BLOCKED"), ("BLOCKED", "PUBLISHING"),
        ("REVIEW_PENDING", "REVIEW_PENDING"), ("REVIEW_PENDING", "PASS"),
        ("PASS", "PASS"),
        ("FAIL", "FAIL"),
    }
    for local in statuses:
        for remote in statuses:
            expected = (local, remote) in allowed
            assert transition_ok(local, remote, "BUSINESS_PUSH_FAILED") is expected, (local, remote)
