"""Daily long-only portfolio simulation with weekly signals and costs."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

from .accounting import annual, metrics
from .risk import RiskConfig, allocate, defense_state


@dataclass(frozen=True)
class SimConfig:
    cost_bps: float = 10.0
    target_vol: float = 0.10
    max_weight: float = 0.10
    max_group_weight: float = 0.20
    corr_threshold: float = 0.70
    lookback: int = 60
    initial_cash: float = 1.0


def _price_matrix(panel, col):
    return panel.pivot_table(index="Date", columns="Ticker", values=col, aggfunc="last").sort_index()


def simulate(opens, closes, events, alloc_fn, cfg: SimConfig):
    dates = [d for d in opens.index if d >= min(events)]
    cash = cfg.initial_cash
    shares = {}
    peak = cfg.initial_cash
    rows = []
    hard_events = []
    hard_seen = False
    for dt in dates:
        if dt in events:
            nav_open = cash + sum(sh * opens.loc[dt, t] for t, sh in shares.items() if pd.notna(opens.loc[dt, t]))
            dd = nav_open / peak - 1
            weights, diag = alloc_fn(events[dt], dt, dd)
            budget = max(0.0, nav_open * (1 - 2 * cfg.cost_bps / 10000))
            target = {t: w * budget for t, w in weights.items()}
            sale = sum(max(0.0, (shares.get(t, 0) * opens.loc[dt, t]) - target.get(t, 0.0))
                       for t in set(shares) | set(target) if pd.notna(opens.loc[dt, t]))
            buy = sum(max(0.0, target.get(t, 0.0) - shares.get(t, 0) * opens.loc[dt, t])
                      for t in set(shares) | set(target) if pd.notna(opens.loc[dt, t]))
            cost = (sale + buy) * cfg.cost_bps / 10000
            new_shares = {}
            for t, val in target.items():
                px = opens.loc[dt, t]
                if pd.notna(px) and px > 0:
                    new_shares[t] = val / px
            cash = nav_open - sum(sh * opens.loc[dt, t] for t, sh in new_shares.items()) - cost
            if cash < -1e-6:
                cash = 0.0
            shares = new_shares
            row = {"date": dt, "nav": None, "cash": cash, "cost": cost, "buy": buy, "sell": sale,
                   "target_weights": weights, "defense": diag.get("defense"),
                   "expected_vol": diag.get("expected_vol"), "clusters": diag.get("clusters"),
                   "reason": diag.get("reason"), "n_holdings": len(weights),
                   "max_weight": max(weights.values()) if weights else 0.0,
                   "max_group_weight": diag.get("max_group_weight")}
        else:
            row = {"date": dt, "nav": None, "cash": cash, "cost": 0.0, "buy": 0.0, "sell": 0.0,
                   "target_weights": {}, "defense": None, "expected_vol": None, "clusters": None,
                   "reason": None, "n_holdings": 0, "max_weight": 0.0, "max_group_weight": None}
        nav = cash + sum(sh * closes.loc[dt, t] for t, sh in shares.items() if pd.notna(closes.loc[dt, t]))
        peak = max(peak, nav)
        row["nav"] = float(nav)
        row["stock"] = float(nav - cash)
        row["drawdown"] = float(nav / peak - 1)
        if row["drawdown"] <= -0.15 and not hard_seen:
            hard_events.append({"date": str(dt.date()), "drawdown": row["drawdown"]})
            hard_seen = True
        rows.append(row)
    daily = pd.DataFrame(rows)
    return daily, hard_events


def equal_alloc(candidates, dt, dd):
    n = len(candidates)
    if n == 0:
        return {}, {"reason": "NO_CONFIRMED", "expected_vol": None, "clusters": 0,
                    "defense": defense_state(dd)}
    return {t: 1.0 / n for t in candidates.ticker}, {"reason": "EQUAL", "expected_vol": None,
                                                       "clusters": 0, "defense": defense_state(dd)}


def risk_alloc(candidates, dt, dd, closes, cfg):
    return allocate(candidates, closes, dt, dd, RiskConfig(
        target_vol=cfg.target_vol, max_weight=cfg.max_weight, max_group_weight=cfg.max_group_weight,
        corr_threshold=cfg.corr_threshold, lookback=cfg.lookback))


def summarize(daily, hard_events, cfg):
    m = metrics(daily)
    m["avg_stock_exposure"] = float((daily.stock / daily.nav).mean())
    m["avg_cash"] = float((daily.cash / daily.nav).mean())
    m["avg_expected_vol"] = float(daily.expected_vol.dropna().mean()) if daily.expected_vol.notna().any() else None
    m["avg_clusters"] = float(daily.clusters.dropna().mean()) if daily.clusters.notna().any() else None
    m["avg_holdings"] = float(daily.n_holdings.mean())
    m["max_single_weight"] = float(daily.max_weight.max())
    m["max_group_weight"] = float(daily.max_group_weight.dropna().max()) if daily.max_group_weight.notna().any() else None
    m["total_cost"] = float(daily.cost.sum())
    m["total_buy"] = float(daily.buy.sum())
    m["total_sell"] = float(daily.sell.sum())
    m["turnover"] = float((daily.buy.sum() + daily.sell.sum()) / (2 * daily.nav.iloc[0])) if len(daily) else None
    m["hard_risk_breaches"] = len(hard_events)
    m["annual"] = annual(daily)
    return m
