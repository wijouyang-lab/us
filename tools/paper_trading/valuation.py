"""Mark-to-market and portfolio risk metrics."""
from __future__ import annotations
import math
from pathlib import Path
import pandas as pd

from tools.paper_trading.account import AccountState, position_shares, positions_view


def mark_to_market(st: AccountState, prices: dict[str, float]) -> dict:
    positions = []
    value = 0.0
    for p in positions_view(st):
        t = p["ticker"]
        if t not in prices or prices[t] is None or prices[t] <= 0:
            raise ValueError(f"missing price for {t}")
        px = float(prices[t]); mv = p["shares"] * px; value += mv
        positions.append({**p, "price": px, "market_value": mv,
                          "unrealized_pnl": mv - p["cost"]})
    nav = st.cash + value
    return {"account_id": st.account_id, "nav": nav, "cash": st.cash,
            "positions_value": value,
            "unrealized_pnl": sum(x["unrealized_pnl"] for x in positions),
            "realized_pnl": st.realized_pnl, "total_fees": st.total_fees,
            "cash_ratio": st.cash / nav if nav else None,
            "positions": positions}


def metrics(nav: pd.Series, rf: pd.Series | None = None) -> dict:
    nav = nav.dropna().astype(float)
    if len(nav) < 2:
        return {"status": "INSUFFICIENT", "days": len(nav)}
    r = nav.pct_change(fill_method=None).dropna()
    years = max((nav.index[-1] - nav.index[0]).days / 365.25, 1e-9)
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1 / years) - 1
    vol = float(r.std(ddof=1) * math.sqrt(252))
    mean = float(r.mean() * 252)
    dd = nav / nav.cummax() - 1
    downside = r[r < 0]
    sortino = mean / (float(downside.std(ddof=1)) * math.sqrt(252)) if len(downside) > 1 else None
    excess_sharpe = None
    if rf is not None:
        ex = (r - rf.reindex(r.index).fillna(0)).dropna()
        ev = float(ex.std(ddof=1) * math.sqrt(252))
        excess_sharpe = float(ex.mean() * 252) / ev if ev else None
    return {"status": "OK", "days": len(nav), "start": str(nav.index[0].date()),
            "end": str(nav.index[-1].date()), "cagr": cagr, "volatility": vol,
            "sharpe_rf0": mean / vol if vol else None,
            "sharpe_excess": excess_sharpe, "sortino": sortino,
            "max_drawdown": float(dd.min()),
            "calmar": cagr / abs(float(dd.min())) if dd.min() < 0 else None,
            "beta_alpha": "requires explicit benchmark; not computed without one"}


def append_nav(path: Path, date: str, snapshot: dict) -> None:
    p = Path(path); row = {"date": date, "nav": snapshot["nav"], "cash": snapshot["cash"],
                           "positions_value": snapshot["positions_value"],
                           "realized_pnl": snapshot["realized_pnl"],
                           "unrealized_pnl": snapshot["unrealized_pnl"]}
    if p.exists():
        d = pd.read_csv(p)
        d = d[d.date.astype(str) != str(date)]
        d = pd.concat([d, pd.DataFrame([row])], ignore_index=True)
    else:
        d = pd.DataFrame([row])
    d.sort_values("date").to_csv(p, index=False)
