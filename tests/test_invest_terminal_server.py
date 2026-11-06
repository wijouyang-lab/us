import json, threading, urllib.request
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from tools.invest_terminal.server import Handler
from tools.paper_trading.engine import PaperEngine


def _post(base, path, body):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=5).read())


def test_local_api_requires_manual_confirmation(tmp_path):
    Handler.engine = PaperEngine(tmp_path)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True); thread.start()
    base = f"http://127.0.0.1:{srv.server_port}"
    try:
        p = _post(base, "/api/paper/propose", {
            "client_order_id": "API-1", "ticker": "AAPL", "side": "BUY", "shares": 1,
            "reference_price": 100, "price_asof": datetime.now(timezone.utc).isoformat(),
            "strategy": "VALUE"})
        assert p["status"] == "PENDING" and p["confirm_token"]
        assert Handler.engine.account()["positions"] == []
        f = _post(base, "/api/paper/confirm", {"order_id": p["order_id"], "token": p["confirm_token"]})
        assert f["fill"]["shares"] == 1
        assert Handler.engine.account()["positions"][0]["ticker"] == "AAPL"
    finally:
        srv.shutdown()
