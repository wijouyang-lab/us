"""Risk metrics for the PAPER-50000 account. Missing prices never become zero."""
from __future__ import annotations
import math
from collections import defaultdict


def concentration(account: dict, prices: dict[str, float] | None = None):
    prices = prices or {}
    cash = float(account.get("cash") or 0)
    positions = account.get("positions") or []
    values = []
    missing = []
    for p in positions:
        ticker = p["ticker"]
        px = prices.get(ticker)
        if px is None:
            missing.append(ticker); continue
        values.append({"ticker": ticker, "value": p["shares"] * px})
    invested = sum(x["value"] for x in values)
    nav = cash + invested
    sectors = {}
    for x in values:
        x["weight"] = x["value"] / nav if nav else None
    return {"cash": cash, "invested": invested, "nav": nav,
            "cash_weight": cash / nav if nav else None,
            "positions": values, "missing_prices": missing,
            "max_position_weight": max((x["weight"] for x in values), default=None),
            "top_positions": sorted(values, key=lambda x: x["value"], reverse=True)[:10],
            "sector_concentration": sectors}


def drawdown(nav_series):
    if not nav_series: return {"max_drawdown": None, "observations": 0}
    peak = None; worst = 0.0
    for x in nav_series:
        v = float(x.get("nav"))
        peak = v if peak is None else max(peak, v)
        if peak: worst = min(worst, v / peak - 1.0)
    return {"max_drawdown": worst, "observations": len(nav_series)}


def portfolio_volatility(returns):
    vals = [float(x) for x in returns if x is not None and math.isfinite(float(x))]
    if len(vals) < 2: return None
    mean = sum(vals) / len(vals)
    var = sum((x - mean) ** 2 for x in vals) / (len(vals) - 1)
    return math.sqrt(var) * math.sqrt(252)


def build_risk(account: dict, prices: dict, nav_series, returns=None):
    c = concentration(account, prices)
    warnings = []
    if not c["positions"]: warnings.append("NO_POSITIONS")
    if c["missing_prices"]: warnings.append("MISSING_PRICES")
    if c["cash_weight"] is not None and c["cash_weight"] > 0.95: warnings.append("CASH_CONCENTRATION_GT_95PCT")
    return {**c, "volatility_annualized": portfolio_volatility(returns or []),
            "drawdown": drawdown(nav_series), "warnings": warnings,
            "status": "AVAILABLE" if c["positions"] else "CASH_ONLY"}
