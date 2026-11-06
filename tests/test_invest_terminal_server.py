import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from http.server import ThreadingHTTPServer
import threading

from tools.invest_terminal.server import Handler, loopback_only
from tools.paper_trading.engine import PaperEngine


def _server(tmp_path):
    Handler.sessions.clear()
    Handler.session_ttl = 3600
    Handler.engine = PaperEngine(tmp_path)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


def _opener():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))


def _get(opener, url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        r = opener.open(req, timeout=5)
        return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def _post(opener, url, body, csrf=None, origin=None, extra=None):
    headers = {"Content-Type": "application/json"}
    if csrf: headers["X-CSRF-Token"] = csrf
    if origin: headers["Origin"] = origin
    headers.update(extra or {})
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    try:
        r = opener.open(req, timeout=5)
        return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def _session(opener, base):
    status, page_headers, body = _get(opener, base + "/terminal.html")
    assert status == 200
    status, api_headers, body = _get(opener, base + "/api/session")
    assert status == 200
    return json.loads(body), page_headers


def test_loopback_binding_guard():
    assert loopback_only("127.0.0.1")
    assert loopback_only("localhost")
    assert not loopback_only("0.0.0.0")
    assert not loopback_only("192.168.1.10")


def test_page_session_and_missing_or_wrong_auth(tmp_path):
    srv, base = _server(tmp_path); opener = _opener()
    try:
        status, headers, _ = _get(opener, base + "/terminal.html")
        assert status == 200
        assert "HttpOnly" in headers.get("Set-Cookie", "")
        assert "dsh_paper_session" in headers.get("Set-Cookie", "")
        assert "Access-Control-Allow-Origin" not in headers
        status, _, _ = _get(_opener(), base + "/api/account")
        assert status == 401
        good, _ = _session(opener, base); assert good["authenticated"] is True
        # wrong cookie has no session
        status, _, _ = _get(_opener(), base + "/api/account", {"Cookie": "dsh_paper_session=wrong"})
        assert status == 401
    finally:
        srv.shutdown()


def test_origin_csrf_and_cross_site_post_fail_closed(tmp_path):
    srv, base = _server(tmp_path); opener = _opener()
    try:
        state, _ = _session(opener, base); csrf = state["csrf_token"]
        body = {"client_order_id": "SEC-1", "ticker": "AAPL", "side": "BUY", "shares": 1,
                "reference_price": 100, "price_asof": datetime.now(timezone.utc).isoformat(), "strategy": "VALUE"}
        # no CSRF
        status, _, _ = _post(opener, base + "/api/paper/propose", body, origin=base)
        assert status == 403
        # bad origin
        status, _, _ = _post(opener, base + "/api/paper/propose", body, csrf=csrf, origin="https://evil.example")
        assert status == 403
        # cross-site fetch metadata
        status, _, _ = _post(opener, base + "/api/paper/propose", body, csrf=csrf, origin=base,
                             extra={"Sec-Fetch-Site": "cross-site"})
        assert status == 403
        # valid same-origin proposal
        status, _, raw = _post(opener, base + "/api/paper/propose", body, csrf=csrf, origin=base)
        assert status == 200
        p = json.loads(raw); assert p["status"] == "PENDING" and p["confirm_token"]
    finally:
        srv.shutdown()


def test_manual_confirmation_and_duplicate_rejection(tmp_path):
    srv, base = _server(tmp_path); opener = _opener()
    try:
        state, _ = _session(opener, base); csrf = state["csrf_token"]
        body = {"client_order_id": "E2E-1", "ticker": "AAPL", "side": "BUY", "shares": 1,
                "reference_price": 100, "price_asof": datetime.now(timezone.utc).isoformat(), "strategy": "VALUE"}
        status, _, raw = _post(opener, base + "/api/paper/propose", body, csrf=csrf, origin=base)
        assert status == 200 and json.loads(raw)["status"] == "PENDING"
        assert Handler.engine.account()["positions"] == []
        # duplicate id
        status, _, _ = _post(opener, base + "/api/paper/propose", body, csrf=csrf, origin=base)
        assert status == 400
        p = json.loads(raw)
        status, _, raw = _post(opener, base + "/api/paper/confirm",
                               {"order_id": p["order_id"], "token": p["confirm_token"]}, csrf=csrf, origin=base)
        assert status == 200
        acct = Handler.engine.account()
        assert acct["positions"] and acct["positions"][0]["ticker"] == "AAPL"
        assert acct["cash"] < 50000.0
        assert len(Handler.engine.history()) == 1
        status, _, raw_acct = _get(opener, base + "/api/account")
        assert status == 200
        safe = json.loads(raw_acct)
        assert safe["account"]["cash"] < 50000.0
        assert "confirm_token" not in json.dumps(safe).lower()
        # confirmation single use
        status, _, _ = _post(opener, base + "/api/paper/confirm",
                             {"order_id": p["order_id"], "token": p["confirm_token"]}, csrf=csrf, origin=base)
        assert status == 400
    finally:
        srv.shutdown()


def test_public_snapshot_has_no_token_even_with_pending_order(tmp_path):
    from tools.invest_terminal.build_snapshot import build
    from pathlib import Path
    e = PaperEngine(tmp_path / "paper")
    p = e.propose(client_order_id="TOKEN-1", ticker="AAPL", side="BUY", shares=1,
                  reference_price=100, price_asof=datetime.now(timezone.utc).isoformat(), strategy="VALUE")
    out = tmp_path / "snap.json"
    build(Path("dashboard/data/dashboard_data.json"), tmp_path / "paper", out)
    text = out.read_text(encoding="utf-8").lower()
    assert p["confirm_token"].lower() not in text
    assert "confirm_token" not in text and "confirmation_token" not in text


def _session_cookie(opener):
    for c in opener.handlers:
        if hasattr(c, "cookiejar"):
            for item in c.cookiejar:
                if item.name == "dsh_paper_session":
                    return item.value
    raise AssertionError("session cookie missing")


def test_session_ttl_expiry_removes_server_session_and_rejects_api(tmp_path):
    srv, base = _server(tmp_path); opener = _opener()
    try:
        state, headers = _session(opener, base)
        sid = _session_cookie(opener)
        assert sid in Handler.sessions
        assert "Max-Age=3600" in headers.get("Set-Cookie", "")
        # force absolute expiry in the server-side store
        Handler.sessions[sid]["expires_at"] = time.monotonic() - 1
        status, _, _ = _get(opener, base + "/api/account")
        assert status == 401
        assert sid not in Handler.sessions
        # old CSRF is now invalid
        body = {"client_order_id": "EXPIRED-1", "ticker": "AAPL", "side": "BUY", "shares": 1,
                "reference_price": 100, "price_asof": datetime.now(timezone.utc).isoformat(), "strategy": "VALUE"}
        status, _, _ = _post(opener, base + "/api/paper/propose", body, csrf=state["csrf_token"], origin=base)
        assert status in (401, 403)
    finally:
        srv.shutdown()


def test_expired_session_requires_page_reentry(tmp_path):
    srv, base = _server(tmp_path); opener = _opener()
    try:
        state, _ = _session(opener, base)
        sid = _session_cookie(opener)
        Handler.sessions[sid]["expires_at"] = time.monotonic() - 1
        status, _, _ = _get(opener, base + "/api/session")
        assert status == 401
        # Re-enter the page to create a fresh session and fresh CSRF.
        status, headers, _ = _get(opener, base + "/terminal.html")
        assert status == 200
        new_sid = _session_cookie(opener)
        assert new_sid != sid and new_sid in Handler.sessions
        status, _, raw = _get(opener, base + "/api/session")
        assert status == 200
        new_state = json.loads(raw)
        assert new_state["csrf_token"] != state["csrf_token"]
    finally:
        srv.shutdown()


def test_expired_sessions_are_purged_from_memory(tmp_path):
    srv, base = _server(tmp_path); opener = _opener()
    try:
        _session(opener, base)
        sid = _session_cookie(opener)
        Handler.sessions[sid]["expires_at"] = time.monotonic() - 1
        # Any new page/session creation purges expired records.
        _get(_opener(), base + "/terminal.html")
        assert sid not in Handler.sessions
    finally:
        srv.shutdown()
