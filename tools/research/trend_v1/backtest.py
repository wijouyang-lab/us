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


class StalePriceError(RuntimeError):
    pass


class MissingExecutionPriceError(RuntimeError):
    pass


def simulate(opens, closes, events, alloc_fn, cfg: SimConfig, raw_closes=None, max_stale_days: int = 5,
             recovery=None, spy_ok_map=None, breadth_ok_map=None):
    dates = [d for d in opens.index if d >= min(events)]
    cash = cfg.initial_cash
    shares = {}
    peak = cfg.initial_cash
    rows = []
    hard_events = []
    hard_seen = False
    stale_days = {}
    missing_exec = 0
    for dt in dates:
        if dt in events:
            missing_held = [t for t in shares if t not in opens.columns or pd.isna(opens.loc[dt, t])]
            if missing_held:
                raise MissingExecutionPriceError(f"missing Open for held {missing_held} at {dt.date()}")
            nav_open = cash + sum(sh * opens.loc[dt, t] for t, sh in shares.items())
            dd = nav_open / peak - 1
            if recovery is not None:
                recovery.update(max(0.0, -dd), bool(spy_ok_map.get(dt, False)) if spy_ok_map else False,
                                bool(breadth_ok_map.get(dt, True)) if breadth_ok_map else True)
            alloc_dd = 0.0 if (recovery is not None and recovery.cap > 0 and -dd >= 0.12) else max(0.0, -dd)
            weights, diag = alloc_fn(events[dt], dt, alloc_dd)
            if recovery is not None:
                weights = {t: w * recovery.cap for t, w in weights.items()}
            target = {t: w * nav_open for t, w in weights.items()}
            missing_new = [t for t in target if t not in opens.columns or pd.isna(opens.loc[dt, t])]
            for t in missing_new:
                target.pop(t, None)
            missing_exec += len(missing_new)

            def trade_cost(vals):
                sale = sum(max(0.0, (shares.get(t, 0) * opens.loc[dt, t]) - vals.get(t, 0.0))
                           for t in set(shares) | set(vals) if pd.notna(opens.loc[dt, t]))
                buy = sum(max(0.0, vals.get(t, 0.0) - shares.get(t, 0) * opens.loc[dt, t])
                          for t in set(shares) | set(vals) if pd.notna(opens.loc[dt, t]))
                return sale, buy, (sale + buy) * cfg.cost_bps / 10000

            sale, buy, cost = trade_cost(target)
            # Charge actual cost once. If full investment would overdraw cash,
            # scale the target by the actual cost, not an arbitrary 2x reserve.
            if sum(target.values()) + cost > nav_open and sum(target.values()) > 0:
                factor = max(0.0, (nav_open - cost) / sum(target.values()))
                target = {t: v * factor for t, v in target.items()}
                sale, buy, cost = trade_cost(target)
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
                   "reason": diag.get("reason"), "n_holdings": len(new_shares),
                   "max_weight": max(weights.values()) if weights else 0.0,
                   "max_group_weight": diag.get("max_group_weight"),
                   "missing_execution": len(missing_new),
                   "recovery_mode": recovery.mode if recovery else None,
                   "recovery_cap": recovery.cap if recovery else None}
        else:
            row = {"date": dt, "nav": None, "cash": cash, "cost": 0.0, "buy": 0.0, "sell": 0.0,
                   "target_weights": {}, "defense": None, "expected_vol": None, "clusters": None,
                   "reason": None, "n_holdings": 0, "max_weight": 0.0, "max_group_weight": None,
                   "missing_execution": 0, "recovery_mode": recovery.mode if recovery else None,
                   "recovery_cap": recovery.cap if recovery else None}
        nav = cash + sum(sh * closes.loc[dt, t] for t, sh in shares.items() if pd.notna(closes.loc[dt, t]))
        peak = max(peak, nav)
        vals = {t: sh * closes.loc[dt, t] for t, sh in shares.items() if pd.notna(closes.loc[dt, t])}
        row["nav"] = float(nav)
        row["stock"] = float(nav - cash)
        row["drawdown"] = float(nav / peak - 1)
        row["risk_state"] = defense_state(max(0.0, -row["drawdown"]))
        row["n_holdings"] = len([v for v in vals.values() if v > 0])
        row["max_weight"] = float(max(vals.values()) / nav) if vals and nav > 0 else 0.0
        if raw_closes is not None:
            for t in shares:
                if pd.isna(raw_closes.loc[dt, t]) if t in raw_closes.columns else True:
                    stale_days[t] = stale_days.get(t, 0) + 1
                else:
                    stale_days[t] = 0
                if stale_days.get(t, 0) > max_stale_days:
                    raise StalePriceError(f"{t} stale for {stale_days[t]} days at {dt.date()}")
        row["stale_holdings"] = sum(1 for t in shares if stale_days.get(t, 0) > 0)
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
    m["stale_holding_days"] = int(daily.stale_holdings.sum()) if "stale_holdings" in daily else 0
    m["total_buy"] = float(daily.buy.sum())
    m["total_sell"] = float(daily.sell.sum())
    m["turnover"] = float((daily.buy.sum() + daily.sell.sum()) / (2 * daily.nav.iloc[0])) if len(daily) else None
    m["hard_risk_breaches"] = len(hard_events)
    m["state_occupancy"] = daily.risk_state.value_counts().to_dict() if "risk_state" in daily else {}
    m["missing_execution_events"] = int(daily.missing_execution.sum()) if "missing_execution" in daily else 0
    m["cash_lockout_days"] = int((daily.recovery_mode == "CASH_DEFENSE").sum()) if "recovery_mode" in daily else 0
    m["recovery_days"] = int((daily.recovery_mode == "RECOVERY").sum()) if "recovery_mode" in daily else 0
    m["annual"] = annual(daily)
    return m
