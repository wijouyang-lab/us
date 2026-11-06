"""Same-origin local-only PAPER-50000 service for Invest Terminal.

Security model:
- bind only 127.0.0.1 (no 0.0.0.0 / public interface);
- serve the Terminal page and API from the same origin;
- HttpOnly, SameSite=Strict local session cookie;
- CSRF header required on every mutating request;
- exact local Origin/Host/Sec-Fetch-Site checks, no wildcard CORS;
- no broker connectivity and no auto-confirm.

The static GitHub Pages page remains read-only. It cannot reach this service.
"""
from __future__ import annotations
import argparse, json, secrets
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from tools.invest_terminal.redaction import public_order, redact
from tools.paper_trading.engine import PaperEngine

ROOT = Path("data/paper_trading")
SNAPSHOT = Path("dashboard/data/invest_terminal_data.json")
PAGE_ROOT = Path(".")
SESSION_COOKIE = "dsh_paper_session"
SESSION_TTL = 3600
STATIC_FILES = {
    "/terminal.html": ("terminal.html", "text/html; charset=utf-8"),
    "/terminal/terminal.css": ("terminal/terminal.css", "text/css; charset=utf-8"),
    "/terminal/terminal.js": ("terminal/terminal.js", "application/javascript; charset=utf-8"),
    "/dashboard/data/invest_terminal_data.json": ("dashboard/data/invest_terminal_data.json", "application/json; charset=utf-8"),
}


def loopback_only(host: str) -> bool:
    return host in ("127.0.0.1", "::1", "localhost")


def safe_public_state(engine: PaperEngine, include_pending_tokens: bool = False) -> dict:
    raw_orders = list(engine.store.orders().values())
    orders = [public_order(o) for o in raw_orders]
    history = redact(engine.store.history())
    state = {"account": redact(engine.account()), "orders": orders, "history": history}
    if include_pending_tokens:
        # Only the authenticated, same-origin local session receives this.
        state["pending_confirmations"] = [
            {"order_id": o["order_id"], "confirm_token": o.get("confirm_token")}
            for o in raw_orders if o.get("status") == "PENDING" and o.get("confirm_token")
        ]
    return state


class Handler(BaseHTTPRequestHandler):
    engine: PaperEngine
    sessions: dict[str, str] = {}
    server_version = "InvestTerminalPaper/1.1"

    # ---------- security helpers ----------
    def _host_ok(self):
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        return loopback_only(host)

    def _origin(self):
        return (self.headers.get("Origin") or "").rstrip("/")

    def _allowed_origins(self):
        p = self.server.server_port
        return {f"http://127.0.0.1:{p}", f"http://localhost:{p}"}

    def _origin_ok(self):
        o = self._origin()
        return bool(o) and o in self._allowed_origins()

    def _cookie(self):
        c = SimpleCookie(self.headers.get("Cookie") or "")
        m = c.get(SESSION_COOKIE)
        return m.value if m else None

    def _session(self):
        sid = self._cookie()
        return sid if sid and sid in self.sessions else None

    def _new_session(self):
        sid = secrets.token_urlsafe(32)
        self.sessions[sid] = secrets.token_urlsafe(32)
        return sid, self.sessions[sid]

    def _send(self, code, body=b"", ctype="application/json; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if body: self.wfile.write(body)

    def _json(self, code, obj, extra=None):
        self._send(code, json.dumps(obj, ensure_ascii=False, default=str).encode(), extra=extra)

    def _require_get(self):
        if not self._host_ok():
            self._json(403, {"error": "host not allowed"}); return False
        if self._session() is None:
            self._json(401, {"error": "authentication required"}); return False
        if self._origin() and not self._origin_ok():
            self._json(403, {"error": "origin not allowed"}); return False
        return True

    def _require(self):
        if not self._host_ok():
            self._json(403, {"error": "host not allowed"}); return False
        if self._session() is None:
            self._json(401, {"error": "authentication required"}); return False
        if not self._origin_ok():
            self._json(403, {"error": "origin not allowed"}); return False
        return True

    def _require_csrf(self):
        token = self.headers.get("X-CSRF-Token") or ""
        expected = self.sessions.get(self._session() or "", "")
        return bool(token) and secrets.compare_digest(token, expected)

    def _read(self):
        try: n = int(self.headers.get("Content-Length") or 0)
        except ValueError: raise ValueError("invalid content length")
        if n > 64_000: raise ValueError("request too large")
        return json.loads(self.rfile.read(n) or b"{}")

    # ---------- HTTP ----------
    def do_OPTIONS(self):
        # No CORS preflight is supported. Cross-origin access fails closed.
        self._json(403, {"error": "cross-origin options disabled"})

    def do_GET(self):
        path = urlparse(self.path).path
        if not self._host_ok():
            return self._json(403, {"error": "host not allowed"})
        if path in ("/", "/terminal.html"):
            sid, _ = self._new_session()
            try:
                file_path, ctype = STATIC_FILES["/terminal.html"]
                body = (PAGE_ROOT / file_path).read_bytes()
            except FileNotFoundError:
                return self._json(404, {"error": "terminal page missing"})
            return self._send(200, body, ctype, {
                "Set-Cookie": f"{SESSION_COOKIE}={sid}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_TTL}",
                "Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'",
            })
        if path in STATIC_FILES:
            if not self._origin_ok() and self._origin():
                return self._json(403, {"error": "origin not allowed"})
            file_path, ctype = STATIC_FILES[path]
            try: body = (PAGE_ROOT / file_path).read_bytes()
            except FileNotFoundError: return self._json(404, {"error": "not found"})
            return self._send(200, body, ctype)
        if path == "/api/session":
            if not self._require_get(): return
            csrf = self.sessions[self._session()]
            state = safe_public_state(self.engine, include_pending_tokens=True)
            return self._json(200, {"authenticated": True, "csrf_token": csrf, **state})
        if path == "/api/account":
            if not self._require_get(): return
            return self._json(200, safe_public_state(self.engine))
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        if not self._require(): return
        if not self._origin_ok():
            return self._json(403, {"error": "origin not allowed"})
        if (self.headers.get("Sec-Fetch-Site") or "same-origin") not in ("same-origin", "none"):
            return self._json(403, {"error": "cross-site request blocked"})
        if not self._require_csrf():
            return self._json(403, {"error": "csrf token required"})
        try:
            body = self._read()
            if self.path == "/api/paper/propose":
                out = self.engine.propose(
                    client_order_id=str(body["client_order_id"]), ticker=str(body["ticker"]),
                    side=str(body["side"]), shares=int(body["shares"]),
                    reference_price=float(body["reference_price"]), price_asof=str(body["price_asof"]),
                    strategy=str(body.get("strategy", "MANUAL")),
                    price_source=str(body.get("price_source", "DASHBOARD_SNAPSHOT")),
                    price_type=str(body.get("price_type", "LAST")))
                return self._json(200, out)
            if self.path == "/api/paper/confirm":
                return self._json(200, self.engine.confirm(str(body["order_id"]), str(body["token"])))
            if self.path == "/api/paper/cancel":
                return self._json(200, self.engine.cancel(str(body["order_id"])))
            return self._json(404, {"error": "not found"})
        except Exception as exc:
            return self._json(400, {"error": f"{type(exc).__name__}: {exc}"})

    def log_message(self, fmt, *args):
        # Never log cookies, CSRF tokens or request bodies.
        print("paper-api:", fmt % args)


def serve(port: int = 8765, root: Path = ROOT):
    if not (1 <= port <= 65535): raise ValueError("invalid port")
    Handler.engine = PaperEngine(root)
    # bind the loopback interface only; never 0.0.0.0
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"PAPER-50000 local API: http://127.0.0.1:{port}/terminal.html (loopback only)")
    srv.serve_forever()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--root", type=Path, default=ROOT)
    a = ap.parse_args(); serve(a.port, a.root)


if __name__ == "__main__":
    main()
