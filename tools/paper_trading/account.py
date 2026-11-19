"""Paper account: one $50,000 account, integer shares, long-only."""
from __future__ import annotations
import json, os, tempfile
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tools.paper_trading.ibkr_costs import fees

ACCOUNT_ID = "PAPER-50000"
INITIAL_CASH = 50000.0


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class Lot:
    lot_id: str
    ticker: str
    strategy: str
    shares: int
    cost_per_share: float
    opened_at: str


@dataclass
class AccountState:
    account_id: str = ACCOUNT_ID
    account_type: str = "PAPER"
    currency: str = "USD"
    real_trading: bool = False
    initial_cash: float = INITIAL_CASH
    cash: float = INITIAL_CASH
    realized_pnl: float = 0.0
    total_fees: float = 0.0
    lots: list[Lot] = field(default_factory=list)


class AccountStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.state_path = self.root / "account_state.json"
        self.ledger_path = self.root / "ledger.jsonl"
        self.root.mkdir(parents=True, exist_ok=True)

    def load(self) -> AccountState:
        if not self.state_path.exists():
            st = AccountState()
            self.save(st)
            return st
        d = json.loads(self.state_path.read_text(encoding="utf-8"))
        d["lots"] = [Lot(**x) for x in d.get("lots", [])]
        allowed = {"account_id","account_type","currency","real_trading","initial_cash",
                   "cash","realized_pnl","total_fees","lots"}
        return AccountState(**{k: v for k, v in d.items() if k in allowed})

    def save(self, st: AccountState) -> None:
        payload = asdict(st)
        payload["updated_at"] = utcnow()
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix=".state-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        os.replace(tmp, self.state_path)

    def append_ledger(self, entry: dict) -> None:
        with self.ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")


def position_shares(st: AccountState, ticker: str) -> int:
    return sum(x.shares for x in st.lots if x.ticker == ticker)


def position_cost(st: AccountState, ticker: str) -> float:
    return sum(x.shares * x.cost_per_share for x in st.lots if x.ticker == ticker)


def positions_view(st: AccountState) -> list[dict]:
    out = {}
    for lot in st.lots:
        if lot.shares <= 0:
            continue
        p = out.setdefault(lot.ticker, {"ticker": lot.ticker, "shares": 0, "cost": 0.0,
                                       "strategies": {}})
        p["shares"] += lot.shares; p["cost"] += lot.shares * lot.cost_per_share
        p["strategies"][lot.strategy] = p["strategies"].get(lot.strategy, 0) + lot.shares
    return [{**v, "avg_cost": v["cost"] / v["shares"]} for v in out.values()]


def credit_dividend(st: AccountState, *, ticker: str, amount_per_share: float,
                    ex_date: str, source: str) -> dict:
    if amount_per_share < 0: raise ValueError("negative dividend")
    shares = position_shares(st, ticker)
    if shares <= 0: raise ValueError("no position")
    cash = shares * amount_per_share; st.cash += cash
    entry = {"type": "DIVIDEND", "timestamp": utcnow(), "ticker": ticker,
             "ex_date": ex_date, "shares": shares, "amount_per_share": amount_per_share,
             "cash": cash, "source": source, "cash_after": st.cash}
    return entry


def apply_split(st: AccountState, *, ticker: str, ratio: float, effective_date: str) -> dict:
    if ratio <= 0: raise ValueError("ratio must be positive")
    changed = 0
    for lot in st.lots:
        if lot.ticker == ticker and lot.shares > 0:
            old = lot.shares
            lot.shares = int(round(old * ratio))
            lot.cost_per_share /= ratio
            changed += lot.shares - old
    if changed == 0: raise ValueError("no position")
    return {"type": "SPLIT", "timestamp": utcnow(), "ticker": ticker,
            "ratio": ratio, "effective_date": effective_date, "share_change": changed}


def execute_fill(st: AccountState, *, ticker: str, side: str, shares: int, reference_price: float,
                 strategy: str, slippage_bps: float, order_id: str) -> dict:
    """Mutate state and return a fill record. Caller must have validated."""
    if side not in ("BUY", "SELL"):
        raise ValueError("side must BUY or SELL")
    if not isinstance(shares, int) or shares <= 0:
        raise ValueError("shares must be a positive integer")
    if reference_price <= 0:
        raise ValueError("reference price must be positive")
    slip = reference_price * slippage_bps / 10000.0
    fill_price = reference_price + slip if side == "BUY" else reference_price - slip
    fee = fees(shares, fill_price, side, utcnow(), layer="forward_estimate")
    total = fee["cost"]
    notional = shares * fill_price
    if side == "BUY":
        debit = notional + total
        if debit > st.cash + 1e-9:
            raise ValueError("insufficient cash")
        st.cash -= debit
        st.total_fees += total
        st.lots.append(Lot(f"{order_id}-L{len(st.lots)+1}", ticker, strategy, shares,
                           debit / shares, utcnow()))
        realized = 0.0
    else:
        if shares > position_shares(st, ticker):
            raise ValueError("insufficient position")
        remaining = shares; proceeds = 0.0; basis = 0.0
        # FIFO by strategy when provided, else FIFO across the ticker.
        for lot in sorted(st.lots, key=lambda x: x.opened_at):
            if remaining <= 0: break
            if lot.ticker != ticker or lot.shares <= 0: continue
            if strategy and lot.strategy != strategy: continue
            take = min(remaining, lot.shares)
            proceeds += take * fill_price
            basis += take * lot.cost_per_share
            lot.shares -= take; remaining -= take
        if remaining:
            raise ValueError("insufficient position for strategy")
        st.cash += proceeds - total
        st.total_fees += total
        st.realized_pnl += proceeds - basis - total
        realized = proceeds - basis - total
    entry = {"type": "FILL", "order_id": order_id, "timestamp": utcnow(),
             "ticker": ticker, "side": side, "shares": shares,
             "reference_price": reference_price, "fill_price": fill_price,
             "notional": notional, "slippage": abs(fill_price - reference_price) * shares,
             "strategy": strategy, **fee, "total_cost": total + abs(fill_price - reference_price) * shares,
             "realized_pnl": realized, "cash_after": st.cash}
    return entry
