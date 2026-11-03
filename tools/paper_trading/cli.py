"""CLI for the isolated $50k paper account."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from tools.paper_trading.engine import PaperEngine
from tools.paper_trading.valuation import append_nav, mark_to_market


def main() -> None:
    ap = argparse.ArgumentParser(description="PAPER only; no broker connectivity")
    ap.add_argument("--root", default="data/paper_trading")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("account")
    sub.add_parser("history")
    p = sub.add_parser("propose")
    p.add_argument("--client-id", required=True); p.add_argument("--ticker", required=True)
    p.add_argument("--side", required=True, choices=["BUY", "SELL", "buy", "sell"])
    p.add_argument("--shares", type=int, required=True); p.add_argument("--price", type=float, required=True)
    p.add_argument("--asof", required=True); p.add_argument("--strategy", required=True)
    p.add_argument("--slip-bps", type=float, default=3.0)
    c = sub.add_parser("confirm"); c.add_argument("--order-id", required=True); c.add_argument("--token", required=True)
    x = sub.add_parser("cancel"); x.add_argument("--order-id", required=True)
    n = sub.add_parser("nav"); n.add_argument("--prices", required=True, help="JSON ticker->price")
    n.add_argument("--date", required=True)
    a = ap.parse_args()
    e = PaperEngine(Path(a.root))
    if a.cmd == "account": print(json.dumps(e.account(), indent=2))
    elif a.cmd == "history": print(json.dumps(e.history(), indent=2))
    elif a.cmd == "propose": print(json.dumps(e.propose(client_order_id=a.client_id, ticker=a.ticker,
        side=a.side.upper(), shares=a.shares, reference_price=a.price, price_asof=a.asof,
        strategy=a.strategy, slippage_bps=a.slip_bps), indent=2))
    elif a.cmd == "confirm": print(json.dumps(e.confirm(a.order_id, a.token), indent=2))
    elif a.cmd == "cancel": print(json.dumps(e.cancel(a.order_id), indent=2))
    elif a.cmd == "nav":
        snap = mark_to_market(e.store.load(), json.loads(a.prices)); append_nav(Path(a.root)/"daily_nav.csv", a.date, snap)
        print(json.dumps(snap, indent=2))


if __name__ == "__main__":
    main()
