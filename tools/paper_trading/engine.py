"""Paper order proposals, confirmation, cancellation and fills.

SQLite is authoritative for account, order and ledger state. JSON/CSV are
exports only. A quote must carry an explicit source and a fresh ISO-8601 UTC
timestamp; future/stale quotes fail closed.
"""
from __future__ import annotations
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path

from tools.paper_trading.account import execute_fill, position_shares, positions_view
from tools.paper_trading.ibkr_costs import fees
from tools.paper_trading.store import SQLiteAccountStore

PENDING = "PENDING"; FILLED = "FILLED"; CANCELLED = "CANCELLED"; EXPIRED = "EXPIRED"; REJECTED = "REJECTED"


def parse_quote_time(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("price_asof required")
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as e:
        raise ValueError("price_asof must be ISO-8601") from e
    if dt.tzinfo is None:
        raise ValueError("price_asof must include timezone (UTC preferred)")
    return dt.astimezone(timezone.utc)


class PaperEngine:
    def __init__(self, root: Path, max_proposal_age_seconds: int = 900,
                 max_price_age_seconds: int = 43200):
        self.root = Path(root); self.store = SQLiteAccountStore(self.root)
        self.max_age = max_proposal_age_seconds; self.max_price_age = max_price_age_seconds

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _check_quote(self, price_asof: str, now: datetime | None = None) -> datetime:
        ts = parse_quote_time(price_asof); now = now or self._now()
        if ts > now + timedelta(seconds=60):
            raise ValueError("price_asof is in the future")
        if (now - ts).total_seconds() > self.max_price_age:
            raise ValueError("stale quote")
        return ts

    def account(self) -> dict:
        st = self.store.load()
        return {"account_id": st.account_id, "account_type": st.account_type,
                "currency": st.currency, "real_trading": st.real_trading,
                "initial_cash": st.initial_cash, "cash": st.cash,
                "realized_pnl": st.realized_pnl, "total_fees": st.total_fees,
                "positions": positions_view(st)}

    def _reserved_cash(self, orders: dict) -> float:
        total = 0.0
        for o in orders.values():
            if o["status"] != PENDING or o["side"] != "BUY": continue
            px = o["reference_price"] * (1 + o["slippage_bps"] / 10000)
            fee = fees(o["shares"], px, "BUY", self._now().isoformat(), layer="forward_estimate")["cost"]
            total += o["shares"] * px + fee
        return total

    def propose(self, *, client_order_id: str, ticker: str, side: str, shares: int,
                reference_price: float, price_asof: str, strategy: str,
                slippage_bps: float = 3.0, price_source: str = "USER_PROVIDED",
                price_type: str = "LAST") -> dict:
        ticker = ticker.upper().strip(); side = side.upper().strip(); strategy = strategy.upper().strip()
        if side not in ("BUY", "SELL"): raise ValueError("side must BUY/SELL")
        if not isinstance(shares, int) or shares <= 0: raise ValueError("shares must be positive integer")
        if reference_price <= 0: raise ValueError("invalid reference price")
        if not (0 <= slippage_bps <= 100): raise ValueError("slippage_bps must be 0..100")
        if strategy not in ("VALUE", "QUALITY", "GARP", "TREND", "DIVIDEND", "HEDGE", "MANUAL"):
            raise ValueError("unknown strategy tag")
        if not price_source.strip() or not price_type.strip():
            raise ValueError("price_source and price_type required")
        ts = self._check_quote(price_asof)
        orders = self.store.orders()
        if any(o.get("client_order_id") == client_order_id for o in orders.values()):
            raise ValueError("duplicate client_order_id")
        st = self.store.load()
        if side == "BUY":
            px = reference_price * (1 + slippage_bps / 10000)
            fee = fees(shares, px, "BUY", self._now().isoformat(), layer="forward_estimate")["cost"]
            need = shares * px + fee
            if need > st.cash - self._reserved_cash(orders):
                raise ValueError("insufficient unreserved cash")
        else:
            reserved_sh = sum(o["shares"] for o in orders.values()
                              if o["status"] == PENDING and o["side"] == "SELL" and o["ticker"] == ticker)
            if shares > position_shares(st, ticker) - reserved_sh:
                raise ValueError("insufficient unreserved position")
        oid = "PAPER-" + secrets.token_hex(8); token = secrets.token_urlsafe(24)
        rec = {"order_id": oid, "client_order_id": client_order_id, "status": PENDING,
               "ticker": ticker, "side": side, "shares": shares,
               "reference_price": reference_price, "price_asof": price_asof,
               "price_asof_utc": ts.isoformat(), "price_source": price_source,
               "price_type": price_type, "strategy": strategy, "slippage_bps": slippage_bps,
               "created_at": self._now().isoformat(), "confirm_token": token,
               "filled_at": None, "fill": None}
        self.store.save_order(rec)
        return rec

    def _expire(self, o: dict) -> None:
        if o["status"] != PENDING: return
        age = (self._now() - datetime.fromisoformat(o["created_at"])).total_seconds()
        if age > self.max_age: o["status"] = EXPIRED

    def confirm(self, order_id: str, confirm_token: str) -> dict:
        o = self.store.orders().get(order_id)
        if not o: raise ValueError("unknown order")
        if o["status"] != PENDING: raise ValueError(f"order not pending: {o['status']}")
        if not secrets.compare_digest(o.get("confirm_token", ""), confirm_token):
            raise ValueError("invalid confirmation token")
        self._expire(o)
        if o["status"] != PENDING:
            self.store.save_order(o); raise ValueError("order expired")
        self._check_quote(o["price_asof"])
        st = self.store.load()
        if o["side"] == "SELL" and o["shares"] > position_shares(st, o["ticker"]):
            raise ValueError("insufficient position")
        fill = execute_fill(st, ticker=o["ticker"], side=o["side"], shares=o["shares"],
                            reference_price=o["reference_price"], strategy=o["strategy"],
                            slippage_bps=o["slippage_bps"], order_id=order_id)
        o["status"] = FILLED; o["filled_at"] = self._now().isoformat(); o["fill"] = fill
        o.pop("confirm_token", None)
        self.store.commit_fill(st, o, fill)
        return o

    def cancel(self, order_id: str) -> dict:
        o = self.store.orders().get(order_id)
        if not o: raise ValueError("unknown order")
        if o["status"] != PENDING: raise ValueError(f"cannot cancel {o['status']}")
        o["status"] = CANCELLED; o["cancelled_at"] = self._now().isoformat(); o.pop("confirm_token", None)
        self.store.save_order(o); return o

    def history(self) -> list[dict]:
        return self.store.history()
