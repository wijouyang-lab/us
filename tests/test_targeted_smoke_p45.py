# -*- coding: utf-8 -*-
import json
from pathlib import Path
import pytest
from tools.investment_research.dividend import dividend_targeted_smoke_p45 as s


DETAIL = """<table>
<tr><td>1</td><td>8-K</td><td><a href="/Archives/edgar/data/1/{acc}/{primary}">{primary}</a></td><td>8-K</td></tr>
<tr><td>2</td><td>EX-99.1</td><td><a href="/Archives/edgar/data/1/{acc}/{exhibit}">{exhibit}</a></td><td>EX-99.1</td></tr>
</table>"""


class Resp:
    def __init__(self, body):
        self.status=200; self.headers={"Content-Type":"text/html"}; self._b=body
    def __enter__(self): return self
    def __exit__(self,*a): pass
    def read(self): return self._b


def test_parse_detail_types():
    h=DETAIL.format(acc="000110465926072929", primary="tm2617177d1_8k.htm", exhibit="tm2617177d1_ex99-1.htm")
    d=s.parse_detail(h)
    assert "8-K" in d["tm2617177d1_8k.htm"] and "EX-99.1" in d["tm2617177d1_ex99-1.htm"]


def test_rejection_detection():
    assert s.is_sec_rejection("Request Rate Threshold Exceeded")
    assert s.is_sec_rejection("Your Request Originates from an Undeclared Automated Tool")
    assert not s.is_sec_rejection("normal filing")


def test_config_blocked_without_request(monkeypatch, tmp_path):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    called=[]
    monkeypatch.setattr(s.urllib.request,"urlopen",lambda *a,**k: called.append(1))
    m=s.run(tmp_path)
    assert m["status"]=="CONFIGURATION_BLOCKED" and m["requests"]==0 and not called


def test_six_request_manifest_complete(monkeypatch, tmp_path):
    def fake(req, timeout=60):
        url=req.full_url
        if "index.html" in url:
            acc=url.split("/")[-2]
            if "18230" in url:
                return Resp(DETAIL.format(acc=acc, primary="tm2617177d1_8k.htm", exhibit="tm2617177d1_ex99-1.htm").encode())
            return Resp(DETAIL.format(acc=acc, primary="bac-20260723.htm", exhibit="exhibit991.htm").encode())
        return Resp(b"official document")
    monkeypatch.setattr(s.urllib.request,"urlopen",fake)
    m=s.run(tmp_path, ua="Research Project research@real.invalid")
    assert m["status"]=="DOWNLOAD_COMPLETE"
    assert m["request_count"]==6
    assert all(t["status"]=="DOWNLOAD_COMPLETE" for t in m["targets"])
    assert (tmp_path/"manifest.json").exists()


def test_rejection_page_fails_manifest(monkeypatch, tmp_path):
    def fake(req, timeout=60):
        return Resp(b"Your Request Originates from an Undeclared Automated Tool")
    monkeypatch.setattr(s.urllib.request,"urlopen",fake)
    m=s.run(tmp_path, ua="Research Project research@real.invalid")
    assert m["status"]=="DOWNLOAD_PARTIAL"
    assert all(t["status"]!="DOWNLOAD_COMPLETE" for t in m["targets"])
