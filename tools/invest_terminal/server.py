"""Local-only PAPER-50000 HTTP service for the Invest Terminal.

Binds 127.0.0.1 by design. No broker connectivity, no auto-confirm, no real
trading. Static GitHub Pages remains read-only; this service is only for local
manual confirmation.
"""
from __future__ import annotations
import argparse, json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tools.paper_trading.engine import PaperEngine

ROOT = Path("data/paper_trading")
SNAPSHOT = Path("dashboard/data/invest_terminal_data.json")


class Handler(BaseHTTPRequestHandler):
    engine: PaperEngine

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers(); self.wfile.write(body)

    def _read(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path.split("?")[0] == "/api/account":
            return self._json(200, self.engine.account())
        if self.path.split("?")[0] == "/api/snapshot":
            return self._json(200, json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.exists() else {})
        return self._json(404, {"error": "not found"})

    def do_POST(self):
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
        print("paper-api:", fmt % args)


def serve(port: int = 8765, root: Path = ROOT):
    Handler.engine = PaperEngine(root)
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"PAPER-50000 local API: http://127.0.0.1:{port} (no broker connectivity)")
    srv.serve_forever()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--root", type=Path, default=ROOT)
    a = ap.parse_args(); serve(a.port, a.root)


if __name__ == "__main__":
    main()
