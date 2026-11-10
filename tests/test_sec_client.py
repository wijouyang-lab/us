# -*- coding: utf-8 -*-
import io, json, urllib.error
import pytest
from tools.investment_research.sec.client import SECClient, SECError


class Resp:
    def __init__(self, body, status=200): self.body=body; self.status=status
    def read(self): return self.body
    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_requires_user_agent(monkeypatch, tmp_path):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    with pytest.raises(SECError, match="SEC_USER_AGENT"):
        SECClient(tmp_path)


def test_cache_avoids_second_download(monkeypatch, tmp_path):
    calls = []
    def fake(req, timeout=0):
        calls.append(req.full_url)
        return Resp(json.dumps({"ok": 1}).encode())
    monkeypatch.setattr("urllib.request.urlopen", fake)
    c = SECClient(tmp_path, user_agent="research test@example.com", min_interval=0.2)
    assert c.get_json("https://data.sec.gov/x", cache_key="x") == {"ok": 1}
    assert c.get_json("https://data.sec.gov/x", cache_key="x") == {"ok": 1}
    assert len(calls) == 1


def test_429_retries_then_succeeds(monkeypatch, tmp_path):
    state = {"n": 0}
    def fake(req, timeout=0):
        state["n"] += 1
        if state["n"] == 1:
            raise urllib.error.HTTPError(req.full_url, 429, "rate", {}, io.BytesIO(b""))
        return Resp(json.dumps({"ok": 2}).encode())
    monkeypatch.setattr("urllib.request.urlopen", fake)
    c = SECClient(tmp_path, user_agent="research test@example.com", min_interval=0.2)
    assert c.get_json("https://data.sec.gov/y", cache_key="y") == {"ok": 2}
    assert state["n"] == 2
