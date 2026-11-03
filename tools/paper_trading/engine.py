"""Paper order proposals, confirmation, cancellation and fills."""
from __future__ import annotations
import json, os, secrets, tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tools.paper_trading.account import (AccountStore, execute_fill, position_shares,
                                         positions_view, utcnow)

PENDING = "PENDING"; FILLED = "FILLED"; CANCELLED = "CANCELLED"; EXPIRED = "EXPIRED"; REJECTED = "REJECTED"


class PaperEngine:
    def __init__(self, root: Path, max_proposal_age_seconds: int = 900):
        self.root = Path(root); self.store = AccountStore(self.root)
        self.orders_path = self.root / "orders.json"; self.max_age = max_proposal_age_seconds

    def _orders(self) -> dict:
        if not self.orders_path.exists(): return {}
        return json.loads(self.orders_path.read_text(encoding="utf-8"))

    def _save_orders(self, d: dict) -> None:
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix=".orders-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh: json.dump(d, fh, indent=2)
        os.replace(tmp, self.orders_path)

    def account(self) -> dict:
        st = self.store.load()
        return {"account_id": st.account_id, "account_type": st.account_type,
                "currency": st.currency, "real_trading": st.real_trading,
                "initial_cash": st.initial_cash, "cash": st.cash,
                "realized_pnl": st.realized_pnl, "total_fees": st.total_fees,
                "positions": positions_view(st)}

    def propose(self, *, client_order_id: str, ticker: str, side: str, shares: int,
                reference_price: float, price_asof: str, strategy: str,
                slippage_bps: float = 3.0) -> dict:
        ticker = ticker.upper().strip(); side = side.upper().strip(); strategy = strategy.upper().strip()
        if side not in ("BUY", "SELL"): raise ValueError("side must BUY/SELL")
        if not isinstance(shares, int) or shares <= 0: raise ValueError("shares must be positive integer")
        if reference_price <= 0: raise ValueError("invalid reference price")
        if strategy not in ("VALUE", "QUALITY", "GARP", "TREND", "DIVIDEND", "HEDGE", "MANUAL"):
            raise ValueError("unknown strategy tag")
        orders = self._orders()
        if any(o.get("client_order_id") == client_order_id for o in orders.values()):
            raise ValueError("duplicate client_order_id")
        if not price_asof or not isinstance(price_asof, str): raise ValueError("price_asof required")
        st = self.store.load()
        reserved_cash = sum(o["shares"] * o["reference_price"] for o in orders.values()
                            if o["status"] == PENDING and o["side"] == "BUY")
        reserved_sh = sum(o["shares"] for o in orders.values()
                          if o["status"] == PENDING and o["side"] == "SELL" and o["ticker"] == ticker)
        if side == "BUY" and shares * reference_price > st.cash - reserved_cash:
            raise ValueError("insufficient unreserved cash")
        if side == "SELL" and shares > position_shares(st, ticker) - reserved_sh:
            raise ValueError("insufficient unreserved position")
        oid = "PAPER-" + secrets.token_hex(8)
        token = secrets.token_urlsafe(24)
        rec = {"order_id": oid, "client_order_id": client_order_id, "status": PENDING,
               "ticker": ticker, "side": side, "shares": shares,
               "reference_price": reference_price, "price_asof": price_asof,
               "strategy": strategy, "slippage_bps": slippage_bps,
               "created_at": utcnow(), "confirm_token": token,
               "filled_at": None, "fill": None}
        orders[oid] = rec; self._save_orders(orders)
        return rec

    def _expire(self, o: dict) -> None:
        if o["status"] == PENDING:
            from datetime import datetime
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(o["created_at"].replace("Z", "+00:00"))).total_seconds()
            if age > self.max_age: o["status"] = EXPIRED

    def confirm(self, order_id: str, confirm_token: str) -> dict:
        orders = self._orders()
        if order_id not in orders: raise ValueError("unknown order")
        o = orders[order_id]
        if o["status"] != PENDING: raise ValueError(f"order not pending: {o['status']}")
        if not secrets.compare_digest(o.get("confirm_token", ""), confirm_token):
            raise ValueError("invalid confirmation token")
        self._expire(o)
        if o["status"] != PENDING: self._save_orders(orders); raise ValueError("order expired")
        st = self.store.load()
        if o["side"] == "SELL" and o["shares"] > position_shares(st, o["ticker"]):
            raise ValueError("insufficient position")
        fill = execute_fill(st, ticker=o["ticker"], side=o["side"], shares=o["shares"],
                            reference_price=o["reference_price"], strategy=o["strategy"],
                            slippage_bps=o["slippage_bps"], order_id=order_id)
        o["status"] = FILLED; o["filled_at"] = utcnow(); o["fill"] = fill
        o.pop("confirm_token", None)
        self.store.save(st); self.store.append_ledger(fill); self._save_orders(orders)
        return o

    def cancel(self, order_id: str) -> dict:
        orders = self._orders()
        if order_id not in orders: raise ValueError("unknown order")
        o = orders[order_id]
        if o["status"] != PENDING: raise ValueError(f"cannot cancel {o['status']}")
        o["status"] = CANCELLED; o["cancelled_at"] = utcnow(); o.pop("confirm_token", None)
        self._save_orders(orders); return o

    def history(self) -> list[dict]:
        p = self.store.ledger_path
        if not p.exists(): return []
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
